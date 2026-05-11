from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.workflows.state import AdvertisementType


IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".webm"})


class MediaValidationError(Exception):
    """Raised when a local asset is missing or does not match the requested media type."""


@dataclass(frozen=True)
class LocalAssetMetadata:
    file_name: str
    local_path_ref: str
    extension: str
    size_bytes: int
    media_type: AdvertisementType


def detect_media_type(local_path: str | Path) -> AdvertisementType:
    extension = Path(local_path).suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return AdvertisementType.IMAGE
    if extension in VIDEO_EXTENSIONS:
        return AdvertisementType.VIDEO
    return AdvertisementType.UNKNOWN


def inspect_local_asset(local_path: str | Path) -> LocalAssetMetadata:
    path = Path(local_path)
    if not path.is_file():
        raise MediaValidationError(f"local asset does not exist: {path}")
    return LocalAssetMetadata(
        file_name=path.name,
        local_path_ref=str(path),
        extension=path.suffix.lower(),
        size_bytes=path.stat().st_size,
        media_type=detect_media_type(path),
    )


def validate_asset_for_ad_type(local_path: str | Path, ad_type: AdvertisementType) -> LocalAssetMetadata:
    metadata = inspect_local_asset(local_path)
    if ad_type is AdvertisementType.UNKNOWN:
        return metadata
    if metadata.media_type != ad_type:
        raise MediaValidationError(
            f"local asset media type {metadata.media_type.value} does not match requested {ad_type.value}"
        )
    return metadata
