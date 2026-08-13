#!/usr/bin/env python3
"""Choose an auditable, monotonic version across preview/publish runs.

Version numbers are identities for package bytes.  Once a preview version has
been observed, different bytes must never reuse it even when the repository's
official metadata is stale.  Conversely, the publish stage must reuse a
matching preview version instead of incrementing it a second time.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CandidateVersionDecision:
    """Machine-readable explanation of one version allocation decision."""

    version: int
    strategy: str
    official_version: int
    official_size: int
    official_md5: str
    existing_candidate_version: int | None
    existing_candidate_size: int | None
    existing_candidate_md5: str | None
    package_size: int
    package_md5: str

    def to_dict(self) -> dict[str, int | str | None]:
        return asdict(self)


def _read_metadata(path: str | Path, *, optional: bool) -> dict[str, int | str] | None:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if optional:
            return None
        raise ValueError(f"required official version file is missing: {source}")
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"version file is unreadable or malformed: {source}") from exc
    try:
        version = int(data["version"])
        size = int(data["size"])
        md5 = str(data["md5"]).lower()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"version metadata is incomplete or invalid: {source}") from exc
    if version <= 0 or size <= 0 or re.fullmatch(r"[0-9a-f]{32}", md5) is None:
        raise ValueError(f"version metadata is incomplete or invalid: {source}")
    return {"version": version, "size": size, "md5": md5}


def decide_candidate_version(
    official_path: str | Path,
    existing_candidate_paths: Iterable[str | Path],
    package_size: int,
    package_md5: str,
) -> CandidateVersionDecision:
    """Allocate one package version without reuse or a two-stage double bump.

    A matching preview is reused even when it is many versions ahead of stale
    official metadata.  If the preview bytes differ, the new package is placed
    strictly after *both* known versions.  This makes legacy gaps explicit and
    monotonic rather than failing forever or reusing a version for new bytes.
    """

    if package_size <= 0 or re.fullmatch(r"[0-9a-f]{32}", package_md5.lower()) is None:
        raise ValueError("current package fingerprint is invalid")
    current_fingerprint = (package_size, package_md5.lower())

    official = _read_metadata(official_path, optional=False)
    assert official is not None
    official_version = int(official["version"])
    official_fingerprint = (int(official["size"]), str(official["md5"]))
    candidates = [
        metadata
        for path in existing_candidate_paths
        if (metadata := _read_metadata(path, optional=True)) is not None
    ]
    if candidates and any(metadata != candidates[0] for metadata in candidates[1:]):
        raise ValueError("existing candidate metadata files disagree")
    candidate = candidates[0] if candidates else None
    candidate_version = int(candidate["version"]) if candidate else None
    candidate_fingerprint = (
        (int(candidate["size"]), str(candidate["md5"])) if candidate else None
    )

    if (
        candidate is not None
        and candidate_fingerprint == current_fingerprint
        and candidate_version is not None
        and (
            candidate_version > official_version
            or (
                candidate_version == official_version
                and current_fingerprint == official_fingerprint
            )
        )
    ):
        # The preview version has already been exposed.  Reuse it for publish,
        # including a legacy preview gap such as official=52, preview=65.
        version = candidate_version
        strategy = (
            "reuse-official-fingerprint"
            if candidate_version == official_version
            and current_fingerprint == official_fingerprint
            else "reuse-matching-preview"
        )
    elif candidate is None:
        if current_fingerprint == official_fingerprint:
            version = official_version
            strategy = "reuse-official-fingerprint"
        else:
            version = official_version + 1
            strategy = "allocate-after-official"
    else:
        # The preview identifies different bytes (or a non-forward version).
        # Never reuse that identity: advance beyond every observed version.
        assert candidate_version is not None
        version = max(official_version, candidate_version) + 1
        strategy = "allocate-after-different-preview"

    return CandidateVersionDecision(
        version=version,
        strategy=strategy,
        official_version=official_version,
        official_size=int(official["size"]),
        official_md5=str(official["md5"]),
        existing_candidate_version=candidate_version,
        existing_candidate_size=int(candidate["size"]) if candidate else None,
        existing_candidate_md5=str(candidate["md5"]) if candidate else None,
        package_size=package_size,
        package_md5=package_md5.lower(),
    )


def choose_candidate_version(
    official_path: str | Path,
    existing_candidate_paths: Iterable[str | Path],
    package_size: int,
    package_md5: str,
) -> int:
    """Compatibility wrapper returning only the selected integer version."""

    return decide_candidate_version(
        official_path,
        existing_candidate_paths,
        package_size,
        package_md5,
    ).version
