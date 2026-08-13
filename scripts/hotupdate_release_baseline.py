#!/usr/bin/env python3
"""Validate hot-update version baselines from the upstream ``latest`` Release.

The repository copies under ``configures/`` can lag a successful Release
transaction.  Version allocation therefore starts from one captured Release
API response plus the version and zip assets downloaded from that same tag.
The zip bytes are checked against both GitHub's size/SHA-256 metadata and the
size/MD5 stored in the version file.  A package manifest is deliberately not a
baseline source: historical Releases can contain a stale inventory manifest,
and the current build will replace it transactionally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SCOPES = {
    "js": {
        "zip": "cn_js_update.zip",
        "version": "version_js.json",
    },
    "scenario": {
        "zip": "cn_scenario_update.zip",
        "version": "version_scenario.json",
    },
}


class ReleaseBaselineError(ValueError):
    """Raised when the captured Release cannot prove a coherent baseline."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseBaselineError(f"{label} is unreadable or malformed: {path}") from exc
    if not isinstance(value, dict):
        raise ReleaseBaselineError(f"{label} must be a JSON object: {path}")
    return value


def _asset_map(release: dict) -> dict[str, dict]:
    if release.get("tag_name") != "latest":
        raise ReleaseBaselineError("Release snapshot is not the exact latest tag")
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ReleaseBaselineError("Release snapshot has no asset list")
    result: dict[str, dict] = {}
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("name"), str):
            raise ReleaseBaselineError("Release snapshot contains a malformed asset")
        name = asset["name"]
        if name in result:
            raise ReleaseBaselineError(f"Release snapshot has duplicate asset name: {name}")
        result[name] = asset
    return result


def _validate_asset_record(asset: dict, expected_name: str) -> dict:
    try:
        asset_id = int(asset["id"])
        size = int(asset["size"])
        digest = str(asset["digest"]).lower()
    except (KeyError, TypeError, ValueError) as exc:
        raise ReleaseBaselineError(
            f"Release asset metadata is incomplete: {expected_name}"
        ) from exc
    if asset.get("name") != expected_name or asset_id <= 0 or size <= 0:
        raise ReleaseBaselineError(f"Release asset metadata is invalid: {expected_name}")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
        raise ReleaseBaselineError(
            f"Release asset has no verifiable SHA-256 digest: {expected_name}"
        )
    return {"id": asset_id, "size": size, "digest": digest}


def _verify_download(path: Path, asset: dict, name: str) -> dict:
    metadata = _validate_asset_record(asset, name)
    if not path.is_file():
        raise ReleaseBaselineError(f"downloaded Release asset is missing: {name}")
    actual_size = path.stat().st_size
    actual_digest = "sha256:" + _sha256(path)
    if actual_size != metadata["size"] or actual_digest != metadata["digest"]:
        raise ReleaseBaselineError(f"downloaded Release asset metadata mismatch: {name}")
    return metadata


def _metadata_pair(
    *,
    zip_name: str,
    version_name: str,
    assets: dict[str, dict],
    asset_dir: Path,
) -> tuple[dict, dict]:
    for name in (zip_name, version_name):
        if name not in assets:
            raise ReleaseBaselineError(f"required Release asset is missing: {name}")

    zip_path = asset_dir / zip_name
    zip_asset = _verify_download(zip_path, assets[zip_name], zip_name)
    version_asset = _verify_download(
        asset_dir / version_name, assets[version_name], version_name
    )
    version = _load_object(asset_dir / version_name, "version metadata")
    try:
        normalized = {
            "version": int(version["version"]),
            "size": int(version["size"]),
            "md5": str(version["md5"]).lower(),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ReleaseBaselineError("Release version metadata is incomplete") from exc
    if (
        normalized["version"] <= 0
        or normalized["size"] <= 0
        or re.fullmatch(r"[0-9a-f]{32}", normalized["md5"]) is None
    ):
        raise ReleaseBaselineError("Release version metadata is invalid")
    if (
        zip_asset["size"] != normalized["size"]
        or _md5(zip_path).lower() != normalized["md5"]
    ):
        raise ReleaseBaselineError(
            "Release version metadata and zip bytes disagree"
        )
    evidence = {
        "version": normalized,
        "zip_asset": {"name": zip_name, **zip_asset},
        "version_asset": {"name": version_name, **version_asset},
    }
    return normalized, evidence


def validate_release_baseline(
    scope: str,
    release_json: str | Path,
    asset_dir: str | Path,
    out_version: str | Path,
    out_candidate: str | Path,
    out_report: str | Path,
) -> dict:
    """Validate stable/optional preview metadata and write canonical baselines."""

    if scope not in SCOPES:
        raise ReleaseBaselineError(f"unsupported scope: {scope}")
    release_path = Path(release_json)
    assets_root = Path(asset_dir)
    release = _load_object(release_path, "Release snapshot")
    assets = _asset_map(release)
    names = SCOPES[scope]
    stable, stable_evidence = _metadata_pair(
        zip_name=names["zip"],
        version_name=names["version"],
        assets=assets,
        asset_dir=assets_root,
    )

    preview_names = {
        key: (
            value.replace(".zip", "_new.zip")
            if key == "zip"
            else value.replace(".json", "_new.json")
        )
        for key, value in names.items()
    }
    preview_present = {
        key: value in assets for key, value in preview_names.items()
    }
    if any(preview_present.values()) and not all(preview_present.values()):
        raise ReleaseBaselineError(
            "Release preview triplet is incomplete: "
            + ", ".join(
                f"{preview_names[key]}={present}"
                for key, present in preview_present.items()
            )
        )

    candidate_path = Path(out_candidate)
    candidate = None
    candidate_evidence = None
    if all(preview_present.values()):
        candidate, candidate_evidence = _metadata_pair(
        zip_name=preview_names["zip"],
        version_name=preview_names["version"],
            assets=assets,
            asset_dir=assets_root,
        )
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    elif candidate_path.exists():
        candidate_path.unlink()

    version_path = Path(out_version)
    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text(
        json.dumps(stable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema": "magireco-cn-hotupdate-release-baseline/v1",
        "status": "PASS",
        "scope": scope,
        "release": {
            "id": release.get("id"),
            "tag_name": release.get("tag_name"),
            "html_url": release.get("html_url"),
            "published_at": release.get("published_at"),
            "snapshot_sha256": _sha256(release_path),
        },
        "stable": stable_evidence,
        "preview": candidate_evidence,
        "repository_configures_trusted": False,
        "zip_bytes_downloaded": True,
    }
    report_path = Path(out_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=sorted(SCOPES), required=True)
    parser.add_argument("--release-json", required=True)
    parser.add_argument("--asset-dir", required=True)
    parser.add_argument("--out-version", required=True)
    parser.add_argument("--out-candidate", required=True)
    parser.add_argument("--out-report", required=True)
    args = parser.parse_args()
    report = validate_release_baseline(
        args.scope,
        args.release_json,
        args.asset_dir,
        args.out_version,
        args.out_candidate,
        args.out_report,
    )
    stable = report["stable"]["version"]
    preview = report["preview"]
    print(
        "validated latest Release baseline: "
        f"scope={args.scope} stable=v{stable['version']} "
        f"preview={('v' + str(preview['version']['version'])) if preview else 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
