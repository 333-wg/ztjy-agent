import pytest

from backend.app.assets.local_search import search_local_assets
from backend.app.assets.media_validation import (
    MediaValidationError,
    detect_media_type,
    validate_asset_for_ad_type,
)
from backend.app.workflows.state import AdvertisementType


def test_local_search_returns_exact_filename_match(tmp_path):
    asset = tmp_path / "may-video.mp4"
    asset.write_bytes(b"video")
    (tmp_path / "other.mp4").write_bytes(b"video")

    results = search_local_assets("may-video.mp4", base_dirs=[tmp_path])

    assert len(results) == 1
    assert results[0].file_name == "may-video.mp4"
    assert results[0].local_path_ref == str(asset)
    assert results[0].media_type == AdvertisementType.VIDEO


def test_local_search_returns_multiple_keyword_candidates(tmp_path):
    (tmp_path / "may-poster.jpg").write_bytes(b"image")
    (tmp_path / "may-video.mp4").write_bytes(b"video")
    (tmp_path / "winter-video.mp4").write_bytes(b"video")

    results = search_local_assets("may", base_dirs=[tmp_path])

    assert [result.file_name for result in results] == [
        "may-poster.jpg",
        "may-video.mp4",
    ]


def test_local_search_filters_by_requested_media_type(tmp_path):
    (tmp_path / "may-poster.jpg").write_bytes(b"image")
    (tmp_path / "may-video.mp4").write_bytes(b"video")

    results = search_local_assets("may", media_type=AdvertisementType.IMAGE, base_dirs=[tmp_path])

    assert [result.file_name for result in results] == ["may-poster.jpg"]


def test_detect_media_type_from_conservative_extensions(tmp_path):
    image = tmp_path / "poster.webp"
    video = tmp_path / "clip.mov"
    unknown = tmp_path / "notes.txt"
    image.write_bytes(b"image")
    video.write_bytes(b"video")
    unknown.write_text("notes")

    assert detect_media_type(image) == AdvertisementType.IMAGE
    assert detect_media_type(video) == AdvertisementType.VIDEO
    assert detect_media_type(unknown) == AdvertisementType.UNKNOWN


def test_validate_asset_accepts_matching_image_and_video_extensions(tmp_path):
    image = tmp_path / "poster.png"
    video = tmp_path / "clip.webm"
    image.write_bytes(b"image")
    video.write_bytes(b"video")

    assert validate_asset_for_ad_type(image, AdvertisementType.IMAGE).media_type == AdvertisementType.IMAGE
    assert validate_asset_for_ad_type(video, AdvertisementType.VIDEO).media_type == AdvertisementType.VIDEO


def test_validate_asset_rejects_media_type_mismatch(tmp_path):
    image = tmp_path / "poster.jpg"
    image.write_bytes(b"image")

    with pytest.raises(MediaValidationError, match="does not match"):
        validate_asset_for_ad_type(image, AdvertisementType.VIDEO)


def test_local_search_does_not_search_outside_configured_base_dirs(tmp_path):
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()
    (outside / "may-video.mp4").write_bytes(b"video")

    results = search_local_assets("may-video.mp4", base_dirs=[inside])

    assert results == []
