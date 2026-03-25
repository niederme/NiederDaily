import pytest
from unittest.mock import MagicMock

from modules.photo import photo_block, _select_best

def test_select_best_prefers_favorites():
    photos = [
        {"id": "1", "date": "2019-03-25", "location": "", "is_favorite": False, "face_count": 0},
        {"id": "2", "date": "2022-03-25", "location": "", "is_favorite": True, "face_count": 0},
        {"id": "3", "date": "2017-03-25", "location": "", "is_favorite": False, "face_count": 1},
    ]
    result = _select_best(photos)
    assert result["id"] == "2"

def test_select_best_falls_back_to_oldest_when_no_favorites():
    photos = [
        {"id": "1", "date": "2018-03-25", "location": "", "is_favorite": False, "face_count": 0},
        {"id": "2", "date": "2015-03-25", "location": "", "is_favorite": False, "face_count": 2},
    ]
    result = _select_best(photos)
    assert result["id"] == "2"  # oldest wins regardless of face_count

def test_select_best_falls_back_to_oldest():
    photos = [
        {"id": "1", "date": "2018-03-25", "location": "", "is_favorite": False, "face_count": 0},
        {"id": "2", "date": "2015-03-25", "location": "", "is_favorite": False, "face_count": 0},
    ]
    result = _select_best(photos)
    assert result["id"] == "2"

def test_photo_block_returns_bytes_and_metadata(mocker, tmp_path):
    fake_jpeg = b'\xff\xd8\xff' + b'\x00' * 100
    fake_photo_dir = tmp_path / "export"
    fake_photo_dir.mkdir()
    fake_photo = fake_photo_dir / "photo.jpg"
    fake_photo.write_bytes(fake_jpeg)

    mock_run = mocker.patch("modules.photo.subprocess.run")
    mock_run.side_effect = [
        # First call: list photos
        MagicMock(returncode=0, stdout="123|2019-03-25|Warwick, NY|true|2\n"),
        # Second call: export (returns the tmp dir path)
        MagicMock(returncode=0, stdout=str(fake_photo_dir)),
    ]

    # Mock TemporaryDirectory to return our controlled tmp_path
    mocker.patch("modules.photo.tempfile.TemporaryDirectory",
                 return_value=mocker.MagicMock(__enter__=lambda s: str(fake_photo_dir),
                                               __exit__=lambda s, *a: None))

    result = photo_block()
    assert result is not None
    img_bytes, meta = result
    assert img_bytes[:3] == b'\xff\xd8\xff'
    assert meta["year"] == "2019"
    assert meta["location"] == "Warwick, NY"
    assert meta["is_favorite"] is True

def test_photo_block_returns_none_when_no_photos(mocker):
    mock_run = mocker.patch("modules.photo.subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="\n")
    result = photo_block()
    assert result is None

def test_photo_block_returns_none_on_applescript_error(mocker):
    mock_run = mocker.patch("modules.photo.subprocess.run")
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    result = photo_block()
    assert result is None
