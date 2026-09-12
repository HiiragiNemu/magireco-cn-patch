#!/usr/bin/env python3
"""Verify per-file Cubism v4 identities against the committed modern authority.

The old global alias ban was invalid because some modern v4 scripts legitimately
retain ids such as 760090. This audit compares exact ``id``/``live2dName``
identity paths only for the deterministically repaired file set.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def identities(obj: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    story = obj.get("story") if isinstance(obj, dict) else None
    groups = {"@0": story} if isinstance(story, list) else story if isinstance(story, dict) else {}
    for group, turns in groups.items():
        if not isinstance(turns, list):
            continue
        for turn_index, turn in enumerate(turns):
            if not isinstance(turn, dict) or not isinstance(turn.get("chara"), list):
                continue
            for chara_index, entry in enumerate(turn["chara"]):
                if not isinstance(entry, dict):
                    continue
                found.append({
                    "group": str(group),
                    "turn": turn_index,
                    "charaIndex": chara_index,
                    "id": entry.get("id"),
                    "live2dNamePresent": "live2dName" in entry,
                    "live2dName": entry.get("live2dName"),
                })
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("madomagi/resource/scenario/json"))
    parser.add_argument("--manifest", type=Path, default=Path("manifests/v4_structure_repair_set.v1.json"))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = load(args.manifest.resolve())
    expected = manifest.get("identityAuthority") or {}
    mismatches: list[dict[str, Any]] = []
    verified = 0
    for rel, expected_entries in sorted(expected.items()):
        path = root / rel
        if not path.is_file():
            mismatches.append({"path": rel, "reason": "missing"})
            continue
        try:
            actual = identities(load(path))
        except Exception as exc:
            mismatches.append({"path": rel, "reason": f"parse: {exc}"})
            continue
        if actual != expected_entries:
            mismatches.append({"path": rel, "reason": "identity mismatch", "expectedEntries": len(expected_entries), "actualEntries": len(actual)})
            continue
        verified += 1

    invalid: list[str] = []
    parseable = 0
    all_paths = sorted(root.rglob("*.json"))
    for path in all_paths:
        try:
            value = load(path)
        except Exception:
            invalid.append(path.relative_to(root).as_posix())
            continue
        if not isinstance(value, dict) or not isinstance(value.get("story"), (dict, list)):
            invalid.append(path.relative_to(root).as_posix())
            continue
        parseable += 1

    legacy_ids = {100191, 100990, 101090, 101190, 300690, 300699, 303190, 303191, 760090}
    retained = [entry for entries in expected.values() for entry in entries if entry.get("id") in legacy_ids]
    status = "PASS" if not mismatches else "FAIL"
    report = {
        "schema": "live2d-v4-identity-audit/v2",
        "status": status,
        "scenarioRoot": str(root),
        "manifest": str(args.manifest.resolve()),
        "authorityFiles": len(expected),
        "verifiedAuthorityFiles": verified,
        "authorityIdentityEntries": sum(len(items) for items in expected.values()),
        "identityMismatches": mismatches,
        "scannedJson": len(all_paths),
        "parseableJson": parseable,
        "knownInvalidJson": invalid,
        "authorityRetainedFormerAliasEntries": len(retained),
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"LIVE2D_V4_IDENTITY_AUDIT_{status} authority_files={len(expected)} verified={verified} identities={report['authorityIdentityEntries']} known_invalid={len(invalid)} retained_authority_aliases={len(retained)}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
