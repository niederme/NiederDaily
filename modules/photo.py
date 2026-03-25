import subprocess
import tempfile
from datetime import date
from pathlib import Path

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
    """Priority: favorite → has faces → oldest → random."""
    favorites = [p for p in photos if p["is_favorite"]]
    if favorites:
        return min(favorites, key=lambda p: p["date"])
    with_faces = [p for p in photos if p["face_count"] > 0]
    if with_faces:
        return min(with_faces, key=lambda p: p["date"])
    return min(photos, key=lambda p: p["date"])


def photo_block() -> tuple | None:
    today = date.today()
    script = LIST_SCRIPT_TEMPLATE.format(month=today.month, day=today.day)
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
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
                return None

            exported_files = list(Path(tmp_dir).iterdir())
            if not exported_files:
                return None

            img_bytes = exported_files[0].read_bytes()

        year = chosen["date"][:4] if chosen["date"] else ""
        meta = {
            "year": year,
            "date": chosen["date"],
            "location": chosen["location"],
            "is_favorite": chosen["is_favorite"],
        }
        return (img_bytes, meta)

    except Exception:
        return None
