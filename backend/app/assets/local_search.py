from __future__ import annotations

from pathlib import Path
from typing import Iterable

from backend.app.assets.media_validation import LocalAssetMetadata, inspect_local_asset
from backend.app.workflows.state import AdvertisementType


def search_local_assets(
    query: str,
    media_type: AdvertisementType | None = None,
    base_dirs: Iterable[str | Path] | None = None,
) -> list[LocalAssetMetadata]:
    normalized_query = query.casefold().strip()
    if not normalized_query:
        return []

    candidates = _iter_configured_files(base_dirs)
    exact_matches: list[LocalAssetMetadata] = []
    keyword_matches: list[LocalAssetMetadata] = []
    for path in candidates:
        metadata = inspect_local_asset(path)
        if media_type not in {None, AdvertisementType.UNKNOWN} and metadata.media_type != media_type:
            continue
        file_name = metadata.file_name.casefold()
        if file_name == normalized_query:
            exact_matches.append(metadata)
        elif normalized_query in file_name:
            keyword_matches.append(metadata)

    return _sort_results(exact_matches or keyword_matches)


def _iter_configured_files(base_dirs: Iterable[str | Path] | None) -> list[Path]:
    paths: list[Path] = []
    for base_dir in base_dirs or []:
        base_path = Path(base_dir)
        if not base_path.is_dir():
            continue
        paths.extend(path for path in base_path.rglob("*") if path.is_file())
    return paths


def _sort_results(results: list[LocalAssetMetadata]) -> list[LocalAssetMetadata]:
    return sorted(results, key=lambda result: (result.file_name.casefold(), result.local_path_ref.casefold()))
