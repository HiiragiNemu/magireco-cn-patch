#!/usr/bin/env python3
"""Build the corrected pass15 final authority/provenance audit.

This builder is intentionally provenance-only.  It combines already verified
runtime ledgers with independently reconstructed cloud-only evidence and never
writes the product JSON files.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "release"

MINIMAL = ROOT / "work/pass15_agent_rebuild"
PASS17 = ROOT / "work/pass17_max_integrated/release"
PASS18_19 = ROOT / "work/pass18_19_rebuilt"
PASS24_25 = ROOT / "work/pass24_25_rebuilt"
PASS10 = (
    MINIMAL
    / "product/magica/i18n_audit/wiki_authority_pass10_equivalence"
    / "equivalence_authority_upgrades.tsv"
)

LEDGER_FIELDS = [
    "sequence",
    "layer",
    "file",
    "key_field",
    "stable_key",
    "field",
    "expected_before",
    "after",
    "runtime_byte_change",
    "counts_toward_residual",
    "original_pass9_residual",
    "authority_tier",
    "authority_type",
    "source_locator",
    "source_record_sha256",
    "wiki_locator",
    "wiki_record_sha256",
    "note",
]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def truth(value: object) -> bool:
    return str(value).lower() == "true"


def pair(row: dict[str, str], key_name: str = "stable_key") -> tuple[str, str, str]:
    return row["file"], row[key_name], row["field"]


def text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    combined = read_tsv(PASS17 / "authority_layer_ledger_571.tsv")
    pass18_19 = read_tsv(PASS18_19 / "pass18_19_authority_ledger_overlay_196.tsv")
    pass24 = read_tsv(PASS24_25 / "pass24_strict_narrow_mechanical_73.tsv")
    pass25 = read_tsv(PASS24_25 / "pass25_extended_glyph_equivalence_52.tsv")
    residual_9380 = read_tsv(
        MINIMAL / "audits/accounting/verified_remaining_residual_9380.tsv"
    )
    pass14_residual = read_tsv(
        ROOT / "work/pass15_agent_structure/pass14_residual_reconstructed.tsv"
    )
    pass10 = read_tsv(PASS10)

    assert len(combined) == 571
    assert len(pass18_19) == 196
    assert len(pass24) == 73
    assert len(pass25) == 52
    assert len(residual_9380) == 9380
    assert len(pass14_residual) == 9643

    pass10_pairs = {pair(row, "key") for row in pass10}
    pass14_pairs = {pair(row, "key") for row in pass14_residual}
    residual_pairs = {pair(row, "key") for row in residual_9380}

    # The earlier pass17 max report compared only with the post-pass minimal
    # ledger and missed five fields that pass10 had already resolved.  Keep the
    # stronger typed Wiki evidence but do not deduct those fields a second time.
    pass17_pass10_overlap = {
        ("cardMagiaMap.json", key, "name")
        for key in ("10228", "30068", "30138", "40138", "40148")
    }
    correction_rows: list[dict[str, str]] = []
    corrected_combined: list[dict[str, str]] = []
    for source in combined:
        row = dict(source)
        p = pair(row)
        if p in pass17_pass10_overlap and row["layer"] == "pass17_first_authority":
            assert p in pass10_pairs and p not in pass14_pairs
            assert truth(row["counts_toward_residual"])
            row["counts_toward_residual"] = "false"
            row["note"] = (
                row["note"]
                + "; stronger typed Wiki evidence retained, but residual was already "
                + "deducted by pass10 linked-Doppel equivalence"
            )
            correction_rows.append(
                {
                    "file": p[0],
                    "stable_key": p[1],
                    "field": p[2],
                    "pass17_value": row["after"],
                    "prior_layer": "pass10",
                    "correction": "retain evidence; set current residual deduction false",
                }
            )
        corrected_combined.append(row)
    assert len(correction_rows) == 5

    ledger: list[dict[str, str]] = [dict(row) for row in corrected_combined]
    ledger.extend(dict(row) for row in pass18_19)

    def append_equivalence_rows(rows: list[dict[str, str]], layer: str) -> None:
        for source in rows:
            is_new = truth(source["current_net_new_residual_delta"])
            value = source["pass14_value"]
            authority_type = (
                "closed_strict_narrow_glyph_mechanical_equivalence"
                if layer == "pass24"
                else "closed_extended_jp_glyph_equivalence"
            )
            note = source["reason"]
            if not is_new:
                note += "; evidence retained but later pass29 already owns the residual deduction"
            ledger.append(
                {
                    "layer": layer,
                    "file": source["file"],
                    "key_field": source["key_field"],
                    "stable_key": source["stable_key"],
                    "field": source["field"],
                    "expected_before": value,
                    "after": value,
                    "runtime_byte_change": "false",
                    "counts_toward_residual": "true" if is_new else "false",
                    "original_pass9_residual": "true",
                    "authority_tier": "3_closed_equivalence",
                    "authority_type": authority_type,
                    "source_locator": (
                        f"pre-AI baseline/{source['file']}/{source['stable_key']}/{source['field']}"
                    ),
                    "source_record_sha256": text_sha(source["baseline"]),
                    "wiki_locator": "",
                    "wiki_record_sha256": "",
                    "note": note,
                }
            )

    append_equivalence_rows(pass24, "pass24")
    append_equivalence_rows(pass25, "pass25")

    for index, row in enumerate(ledger, 1):
        row["sequence"] = str(index)
    assert len(ledger) == 892

    evidence_pairs = {pair(row) for row in ledger}
    assert len(evidence_pairs) == 863
    assert len([row for row in ledger if truth(row["runtime_byte_change"])]) == 357

    # Recompute current residual directly from the independently verified 9380
    # ledger rather than trusting historical arithmetic.
    combined_remove = residual_pairs & {pair(row) for row in corrected_combined}
    pass18_remove = residual_pairs & {pair(row) for row in pass18_19}
    pass24_remove = residual_pairs & {pair(row) for row in pass24}
    pass25_remove = residual_pairs & {
        pair(row) for row in pass25 if truth(row["current_net_new_residual_delta"])
    }
    assert len(combined_remove) == 101
    assert len(pass18_remove) == 196
    assert len(pass24_remove) == 73
    assert len(pass25_remove) == 51
    removal = combined_remove | pass18_remove | pass24_remove | pass25_remove
    assert len(removal) == 421
    remaining = [row for row in residual_9380 if pair(row, "key") not in removal]
    assert len(remaining) == 8959

    write_tsv(OUT / "authority_layer_ledger_892.tsv", ledger, LEDGER_FIELDS)
    write_tsv(
        OUT / "pass17_pass10_overlap_correction_5.tsv",
        correction_rows,
        ["file", "stable_key", "field", "pass17_value", "prior_layer", "correction"],
    )
    write_tsv(
        OUT / "remaining_residual_8959.tsv",
        remaining,
        list(residual_9380[0]),
    )
    steps = [
        {
            "step": "verified_minimal_postpass",
            "residual_before": 9643,
            "new_unique_deductions": 263,
            "residual_after": 9380,
            "note": "independent fail-closed minimal rebuild",
        },
        {
            "step": "pass17_corrected_new",
            "residual_before": 9380,
            "new_unique_deductions": 101,
            "residual_after": 9279,
            "note": "108 evidence rows: 1 existing-layer overlap, 1 outside original residual, 5 already pass10",
        },
        {
            "step": "pass18_19_rebuilt",
            "residual_before": 9279,
            "new_unique_deductions": 196,
            "residual_after": 9083,
            "note": "34 exact official-family names + 162 guarded strict equivalents",
        },
        {
            "step": "pass24_rebuilt",
            "residual_before": 9083,
            "new_unique_deductions": 73,
            "residual_after": 9010,
            "note": "proper disjoint narrow-glyph/mechanical set",
        },
        {
            "step": "pass25_rebuilt",
            "residual_before": 9010,
            "new_unique_deductions": 51,
            "residual_after": 8959,
            "note": "52 evidence rows; one sequential overlap already deducted by pass29",
        },
    ]
    write_tsv(
        OUT / "residual_deduction_steps.tsv",
        steps,
        ["step", "residual_before", "new_unique_deductions", "residual_after", "note"],
    )

    summary = {
        "schema": "magireco-cn-authority-pass15-final-ledger/v1",
        "status": "PASS",
        "authority_order": [
            "official_cn_dump_20221010",
            "frozen_hiiraginemu_magireco_wiki_data",
            "closed_strict_equivalence",
            "manual_or_llm_last",
        ],
        "pass9_original_residual": 11055,
        "verified_pass14_residual": 9643,
        "post_pass14_evidence_rows": len(ledger),
        "post_pass14_unique_fields": len(evidence_pairs),
        "runtime_byte_changes": sum(truth(row["runtime_byte_change"]) for row in ledger),
        "provenance_only_rows": sum(not truth(row["runtime_byte_change"]) for row in ledger),
        "post_pass14_net_unique_residual_deductions": 684,
        "verified_remaining_residual": len(remaining),
        "old_8722_claim_accepted": False,
        "accounting_corrections": {
            "pass17_rows_already_pass10": 5,
            "pass17_new_unique_deductions": 101,
            "old_pass24_86_double_counted_pass25_item_rows": 13,
            "proper_pass24": 73,
            "pass25_evidence": 52,
            "pass25_later_pass29_overlap": 1,
            "pass25_net_new": 51,
            "pass26_27_new_unique_deductions": 0,
            "pass28_rows_already_pass12": 10,
        },
        "layers": dict(Counter(row["layer"] for row in ledger)),
        "files": dict(Counter(row["file"] for row in ledger)),
        "output_sha256": {},
    }
    summary_path = OUT / "authority_layer_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    for path in sorted(OUT.iterdir()):
        if path.name != summary_path.name and path.is_file():
            summary["output_sha256"][path.name] = sha256(path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    checksums = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            checksums.append(f"{sha256(path)}  {path.name}")
    (OUT / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
