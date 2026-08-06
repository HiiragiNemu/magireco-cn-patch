from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE / "extracted"


def csv_count(name: str) -> int:
    with (HERE / name).open("r", encoding="utf-8-sig", newline="") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    inventory = json.loads((HERE / "inventory.json").read_text("utf-8"))
    inv_paths = {row["path"] for row in inventory}
    disk_paths = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file()}
    assert len(inventory) == 10183
    assert inv_paths == disk_paths
    assert sum(row["size"] for row in inventory) == 686629480
    assert csv_count("inventory.csv") == len(inventory)

    summary = json.loads((HERE / "summary.json").read_text("utf-8"))
    assert summary["replacement_manifest"] == {
        "entries": 8558,
        "listed_match": 570,
        "listed_mismatch": 6121,
        "listed_missing": 1867,
        "actual_unlisted": 3492,
        "status_by_extension": summary["replacement_manifest"]["status_by_extension"],
    }
    assert csv_count("replacement_manifest_audit.csv") == 8558

    comparison = json.loads((HERE / "comparison_summary.json").read_text("utf-8"))
    assert comparison["text_authority_file_candidates"] == 144
    assert comparison["strong_cn_text_literal_count"] == 879
    assert comparison["strong_cn_same_geometry_png_count"] == 7
    assert comparison["png_same_path_count"] == 8865
    assert comparison["png_same_geometry_count"] == 8827
    assert comparison["totentanz_index_dependencies_missing_from_tar"] == 8
    assert csv_count("authoritative_text_candidates.csv") == 144
    assert csv_count("strong_cn_text_literals.csv") == 879
    assert csv_count("web_png_geometry_candidates.csv") == 8865

    png_rows = json.loads((HERE / "strong_cn_png_candidates.json").read_text("utf-8"))
    expected_png = {
        "resource/image_web/common/global/global_battle.png",
        "resource/image_web/common/global/global_gacha.png",
        "resource/image_web/common/global/global_memoria.png",
        "resource/image_web/common/global/global_mission.png",
        "resource/image_web/common/global/global_quest.png",
        "resource/image_web/common/global/global_shop.png",
        "resource/image_web/common/global/global_team.png",
    }
    assert {row["path"] for row in png_rows} == expected_png
    assert all(row["same_geometry"] for row in png_rows)

    curated = json.loads((HERE / "curated_global_icons.json").read_text("utf-8"))
    update2 = [row for row in curated if "/update2/" in row["path"]]
    assert len(update2) == 6
    assert sum(row["visual_language_class"] == "japanese_residue" for row in update2) == 5
    assert sum(row["visual_language_class"] == "shared_han_ambiguous" for row in update2) == 1
    assert all(int(row["old_text_reference_count"]) == 0 for row in update2)

    report = (HERE / "report.md").read_text("utf-8")
    assert len(report) > 10000
    for required in (
        "replacement.js",
        "strong_cn_text_literals",
        "global_gacha.png",
        "update2",
        "japanese_residue",
        "data-nativeimgkey",
    ):
        assert required in report

    artifact_names = [
        "report.md",
        "analyze_old_magica.py",
        "compare_totentanz.py",
        "validate_outputs.py",
        "inventory.json",
        "inventory.csv",
        "candidate_inventory.json",
        "candidate_inventory.csv",
        "summary.json",
        "replacement_manifest.json",
        "replacement_manifest_audit.csv",
        "module_path_map.csv",
        "dependencies.json",
        "localizable_strings.csv",
        "text_literal_authority.csv",
        "strong_cn_text_literals.csv",
        "authoritative_text_candidates.csv",
        "old_vs_totentanz_inventory.csv",
        "web_png_geometry_candidates.csv",
        "curated_global_icons.csv",
        "strong_cn_png_candidates.csv",
        "module_map_comparison.csv",
        "totentanz_index_dependencies.csv",
        "comparison_summary.json",
        "update2-comparison.png",
        "global-root-comparison.png",
        "commands.log",
        "archive-test.log",
        "extract.log",
        "source_hashes.json",
    ]
    hashes = []
    for name in artifact_names:
        path = HERE / name
        assert path.is_file(), name
        hashes.append({"path": str(path), "size": path.stat().st_size, "sha256": sha256(path)})
    (HERE / "artifact_hashes.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2), "utf-8")

    result = {
        "status": "pass",
        "inventory_files": len(inventory),
        "inventory_bytes": sum(row["size"] for row in inventory),
        "authoritative_text_candidate_files": 144,
        "strong_cn_text_literals": 879,
        "strong_cn_png_candidates": 7,
        "update2_japanese_residue": 5,
        "update2_shared_han_ambiguous": 1,
        "hashed_artifacts": len(hashes),
    }
    (HERE / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
