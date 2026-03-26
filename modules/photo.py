from __future__ import annotations

import logging
import subprocess
import tempfile
import threading
from datetime import date
from datetime import datetime
from pathlib import Path

try:
    import Photos
    from Foundation import NSSortDescriptor, NSURL
except ImportError:  # pragma: no cover - exercised in integration environments
    Photos = None
    NSSortDescriptor = None
    NSURL = None

log = logging.getLogger(__name__)

LIST_SCRIPT_TEMPLATE = """\
set targetMonth to {month}
set targetDay to {day}
set output to ""
tell application "Photos"
    repeat with m in media items
        set d to date of m
        if month of d as integer = targetMonth and day of d as integer = targetDay then
            set yr to year of d as string
            set loc to ""
            try
                set loc to location of m
                if loc is missing value then set loc to ""
            end try
            set fav to favorite of m
            set fc to 0
            -- face_count is always 0 since Photos.app does not expose face count via AppleScript
            set output to output & (id of m) & "|" & yr & "-" & my pad(month of d as integer) & "-" & my pad(day of d as integer) & "|" & loc & "|" & fav & "|" & fc & "\\n"
        end if
    end repeat
end tell
return output

on pad(n)
    if n < 10 then return "0" & n
    return n as string
end pad
"""

EXPORT_SCRIPT_TEMPLATE = """\
tell application "Photos"
    set m to media item id "{photo_id}"
    set tmpPath to "{tmp_path}"
    export {{m}} to POSIX file tmpPath with using originals
end tell
return tmpPath
"""


def _select_best(photos: list) -> dict:
    """Priority: favorited photos first, then oldest by date."""
    favorites = [p for p in photos if p["is_favorite"]]
    if favorites:
        return min(favorites, key=lambda p: p["date"])
    return min(photos, key=lambda p: p["date"])


def _photo_readable_statuses() -> set[int]:
    if Photos is None:
        return set()
    statuses = {Photos.PHAuthorizationStatusAuthorized}
    limited = getattr(Photos, "PHAuthorizationStatusLimited", None)
    if limited is not None:
        statuses.add(limited)
    return statuses


def photo_access_granted(prompt: bool = False) -> bool:
    if Photos is None:
        return False

    if hasattr(Photos.PHPhotoLibrary, "authorizationStatusForAccessLevel_"):
        status = Photos.PHPhotoLibrary.authorizationStatusForAccessLevel_(Photos.PHAccessLevelReadWrite)
    else:
        status = Photos.PHPhotoLibrary.authorizationStatus()

    if status in _photo_readable_statuses():
        return True
    if not prompt:
        return False

    done = threading.Event()
    result = {"status": status}

    if hasattr(Photos.PHPhotoLibrary, "requestAuthorizationForAccessLevel_handler_"):
        def completion(new_status):
            result["status"] = int(new_status)
            done.set()

        Photos.PHPhotoLibrary.requestAuthorizationForAccessLevel_handler_(Photos.PHAccessLevelReadWrite, completion)
    elif hasattr(Photos.PHPhotoLibrary, "requestAuthorization_"):
        def completion(new_status):
            result["status"] = int(new_status)
            done.set()

        Photos.PHPhotoLibrary.requestAuthorization_(completion)
    else:
        return False

    done.wait(10)
    return result["status"] in _photo_readable_statuses()


def _native_photo_block() -> tuple | None:
    if Photos is None or not photo_access_granted():
        return None

    today = date.today()
    try:
        options = Photos.PHFetchOptions.alloc().init()
        options.setSortDescriptors_([NSSortDescriptor.sortDescriptorWithKey_ascending_("creationDate", True)])
        assets = Photos.PHAsset.fetchAssetsWithMediaType_options_(Photos.PHAssetMediaTypeImage, options)

        photos = []
        for idx in range(assets.count()):
            asset = assets.objectAtIndex_(idx)
            created = asset.creationDate()
            if created is None:
                continue
            created_dt = datetime.fromtimestamp(created.timeIntervalSince1970())
            if created_dt.month != today.month or created_dt.day != today.day:
                continue

            photos.append({
                "id": str(asset.localIdentifier()),
                "date": created_dt.date().isoformat(),
                "location": "",
                "is_favorite": bool(asset.isFavorite()),
                "face_count": 0,
                "_asset": asset,
            })

        if not photos:
            return None

        chosen = _select_best(photos)
        asset = chosen["_asset"]
        resources = list(Photos.PHAssetResource.assetResourcesForAsset_(asset) or [])
        preferred_types = [
            getattr(Photos, "PHAssetResourceTypeFullSizePhoto", None),
            getattr(Photos, "PHAssetResourceTypePhoto", None),
        ]
        resource = None
        for resource_type in preferred_types:
            if resource_type is None:
                continue
            for candidate in resources:
                if candidate.type() == resource_type:
                    resource = candidate
                    break
            if resource is not None:
                break
        if resource is None and resources:
            resource = resources[0]
        if resource is None:
            log.warning("PhotoKit found asset %s but no exportable resources", chosen["id"])
            return None

        with tempfile.TemporaryDirectory() as tmp_dir:
            filename = resource.originalFilename() or "onthisday.jpeg"
            out_path = Path(tmp_dir) / filename
            url = NSURL.fileURLWithPath_(str(out_path))
            request_options = Photos.PHAssetResourceRequestOptions.alloc().init()
            request_options.setNetworkAccessAllowed_(True)

            done = threading.Event()
            result = {"error": None}

            def completion(error):
                result["error"] = error
                done.set()

            Photos.PHAssetResourceManager.defaultManager().writeDataForAssetResource_toFile_options_completionHandler_(
                resource,
                url,
                request_options,
                completion,
            )

            if not done.wait(30):
                log.warning("PhotoKit export timed out for photo %s", chosen["id"])
                return None
            if result["error"] is not None:
                log.warning("PhotoKit export failed for photo %s: %s", chosen["id"], result["error"])
                return None
            if not out_path.exists():
                log.warning("PhotoKit export reported success but produced no file for photo %s", chosen["id"])
                return None

            img_bytes = out_path.read_bytes()
            img_suffix = out_path.suffix.lower().lstrip(".")

        year = chosen["date"][:4] if chosen["date"] else ""
        return (
            img_bytes,
            {
                "year": year,
                "date": chosen["date"],
                "location": chosen["location"],
                "is_favorite": chosen["is_favorite"],
                "format": img_suffix or "jpeg",
            },
        )
    except Exception:
        log.warning("PhotoKit path failed for on-this-day photo block", exc_info=True)
        return None


def _applescript_photo_block() -> tuple | None:
    today = date.today()
    script = LIST_SCRIPT_TEMPLATE.format(month=today.month, day=today.day)
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            log.warning("Photos list AppleScript failed: %s", result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
            return None

        photos = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) < 5:
                continue
            photo_id, date_str, location, is_fav_str, face_count_str = parts[:5]
            photos.append({
                "id": photo_id.strip(),
                "date": date_str.strip(),
                "location": location.strip(),
                "is_favorite": is_fav_str.strip().lower() == "true",
                "face_count": int(face_count_str.strip()) if face_count_str.strip().isdigit() else 0,
            })

        if not photos:
            return None

        chosen = _select_best(photos)

        with tempfile.TemporaryDirectory() as tmp_dir:
            export_script = EXPORT_SCRIPT_TEMPLATE.format(
                photo_id=chosen["id"], tmp_path=tmp_dir
            )
            export_result = subprocess.run(
                ["osascript", "-e", export_script],
                capture_output=True, text=True, timeout=30
            )
            if export_result.returncode != 0:
                log.warning("Photos export AppleScript failed for photo %s: %s", chosen["id"], export_result.stderr.strip() or export_result.stdout.strip() or f"exit {export_result.returncode}")
                return None

            exported_files = list(Path(tmp_dir).iterdir())
            if not exported_files:
                log.warning("Photos export succeeded but produced no files for photo %s", chosen["id"])
                return None

            exported = exported_files[0]
            img_bytes = exported.read_bytes()
            img_suffix = exported.suffix.lower().lstrip(".")  # e.g. "jpg", "heic", "png"

        year = chosen["date"][:4] if chosen["date"] else ""
        meta = {
            "year": year,
            "date": chosen["date"],
            "location": chosen["location"],
            "is_favorite": chosen["is_favorite"],
            "format": img_suffix or "jpeg",
        }
        return (img_bytes, meta)

    except Exception:
        log.warning("Failed to build on-this-day photo block via AppleScript", exc_info=True)
        return None


def photo_block() -> tuple | None:
    native_result = _native_photo_block()
    if native_result is not None:
        return native_result
    return _applescript_photo_block()
