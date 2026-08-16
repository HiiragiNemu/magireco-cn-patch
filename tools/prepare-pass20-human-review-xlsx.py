from __future__ import annotations

import csv
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
OUT = ROOT / "_artifacts/spreadsheet_build/v26_translation_review_1565_input.json"
SCHEMA = "magireco-cn-v26-translation-human-review-workbook/5"


def load_final_values_contract():
    path = Path(__file__).with_name("pass20_final_values_contract.py")
    spec = importlib.util.spec_from_file_location("pass20_final_values_contract", path)
    if spec is None or spec.loader is None:
        raise SystemExit("final-values contract could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FINAL_VALUES = load_final_values_contract()


def load_tsv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise SystemExit(f"TSV byte contract drifted: {path}")
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        rows = list(reader)
    if not reader.fieldnames or any(None in row for row in rows):
        raise SystemExit(f"TSV structure drifted: {path}")
    return rows


def unique(rows: list[dict[str, str]], label: str) -> dict[str, dict[str, str]]:
    result = {row.get("item_id", ""): row for row in rows}
    if "" in result or len(result) != len(rows):
        raise SystemExit(f"{label} item_id contract drifted")
    return result


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_json(value: object) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()


source_path = AUDIT / "pass20_remaining_manual_review.tsv"
priority_path = AUDIT / "pass20_priority_manual_review.tsv"
inventory_path = AUDIT / "pass20_machine_source_inventory.tsv"
shadow_path = AUDIT / "pass20_authority_shadowed_machine_items.tsv"
resolution_path = AUDIT / "pass20_authority_resolutions.tsv"
sealed_path = AUDIT / "dsv4_terminal_handoff/full_review.tsv"
target_path = AUDIT / "pass20_product_targets.json"
adoption_path = AUDIT / "pass21_user_directed_suggested_adoptions.tsv"

source_rows = load_tsv(source_path)
priority_rows = load_tsv(priority_path)
inventory_rows = load_tsv(inventory_path)
shadow_rows = load_tsv(shadow_path)
resolution_rows = load_tsv(resolution_path)
sealed_rows = load_tsv(sealed_path)
adoption_rows = load_tsv(adoption_path)
source = unique(source_rows, "human queue")
priority = unique(priority_rows, "priority queue")
inventory = unique(inventory_rows, "machine inventory")
shadow = unique(shadow_rows, "higher-authority shadow")
resolutions = unique(resolution_rows, "authority resolutions")
sealed = unique(sealed_rows, "sealed review")
adoptions = unique(adoption_rows, "user-directed suggested adoptions")

expected = {
    "inventory": 1589, "human": 1565, "priority": 199, "approved": 1366,
    "excluded": 347, "authority": 323, "shadowed": 24,
}
actual = {
    "inventory": len(inventory), "human": len(source), "priority": len(priority),
    "approved": len(source) - len(priority), "excluded": len(resolutions) + len(shadow),
    "authority": len(resolutions), "shadowed": len(shadow),
}
if actual != expected:
    raise SystemExit(f"queue partition drifted: {actual}")
if not set(priority) < set(source):
    raise SystemExit("priority queue is not a strict subset of human queue")
approved_ids = set(source) - set(priority)
if any(source[item_id].get("parent_verdict") != "approved" for item_id in approved_ids):
    raise SystemExit("non-priority human queue item is not DS-approved")
if set(inventory) != set(source) | set(shadow) or set(source) & set(shadow):
    raise SystemExit("1589 machine inventory partition drifted")
if set(resolutions) & set(shadow):
    raise SystemExit("authority and shadow exclusions overlap")
if set(sealed) != set(source) | set(resolutions) | set(shadow):
    raise SystemExit("1912 sealed partition drifted")
if len(adoptions) != 29 or not set(adoptions) < set(source):
    raise SystemExit("29-row user-directed suggested adoption set drifted")
for item_id, adoption in adoptions.items():
    row = source[item_id]
    binding = {
        "source_index": row.get("source_index", ""),
        "stable_business_key": row.get("stable_business_key", ""),
        "source_key": row.get("source_key", ""),
        "source_text": row.get("japanese_or_source_original", ""),
        "current_cn": row.get("current_cn", ""),
        "ds_suggested_cn": row.get("suggested_cn", ""),
    }
    if any(adoption.get(field, "") != value for field, value in binding.items()):
        raise SystemExit(f"user-directed suggestion adoption binding drifted: {item_id}")
    if not adoption.get("adopted_cn", ""):
        raise SystemExit(f"user-directed adopted Chinese is empty: {item_id}")

target_raw = target_path.read_bytes()
target_payload = json.loads(target_raw.decode("utf-8"))
if target_payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1" or target_payload.get("status") != "PASS":
    raise SystemExit("target manifest contract drifted")
target_rows = target_payload.get("items")
if not isinstance(target_rows, list):
    raise SystemExit("target manifest items missing")
targets = unique(target_rows, "target manifest")
if set(targets) != set(source):
    raise SystemExit("target manifest does not match 1565 human queue")
target_indices = {str(row["item_id"]): index for index, row in enumerate(target_rows)}
if len(target_indices) != len(target_rows):
    raise SystemExit("target manifest external index is not unique")
target_contract_sha256 = sha256(target_raw).hexdigest()

def review_row(item_id: str, partition: str) -> dict[str, object]:
    row = source[item_id]
    sealed_row = sealed[item_id]
    target = targets[item_id]
    original = row.get("japanese_or_source_original", "")
    expected_text_hash = sha256(original.encode("utf-8")).hexdigest()
    if sealed_row.get("source_text_sha256") != expected_text_hash:
        raise SystemExit(f"sealed source text hash drifted: {item_id}")
    queue_enrichment_fields = {
        "human_decision", "reviewer", "timestamp", "final_value", "human_revision", "human_notes",
        "allowed_human_decisions", "review_status", "review_scope_status", "application_policy",
        "effective_cn", "effective_tier", "effective_source_file", "effective_source_line",
        "shadowed_by_higher_authority", "product_write_forbidden",
        "canonical_write_allowed_after_human_gate",
    }
    if any(row.get(key, "") != sealed_row.get(key, "") for key in row if key not in queue_enrichment_fields):
        raise SystemExit(f"queue/sealed source drifted: {item_id}")
    current_cn = row.get("current_cn", "")
    adoption = adoptions.get(item_id)
    final_seed, seed_origin = FINAL_VALUES.seed_for_source(
        row, adoption["adopted_cn"] if adoption else "",
    )
    if not original or not current_cn or not final_seed:
        raise SystemExit(f"visible review text is empty: {item_id}")
    return {
        "item_id": item_id,
        "original": original,
        "current_cn": current_cn,
        "final_seed": final_seed,
        "seed_origin": seed_origin,
        "seed_final_sha256": sha256(final_seed.encode("utf-8")).hexdigest(),
        "source_text_sha256": expected_text_hash,
        "source_record_sha256": FINAL_VALUES.source_record_sha256(row),
        "target_row_sha256": FINAL_VALUES.target_contract_sha256(target),
        "stable_business_key": row.get("stable_business_key", ""),
        "target_manifest_index": target_indices[item_id],
        "partition": partition,
    }


priority_rank = {"correction": 0, "unresolved": 1, "manual-required": 2}
priority_order = sorted(
    priority,
    key=lambda item_id: (priority_rank.get(source[item_id].get("parent_verdict", ""), 9), int(source[item_id].get("source_index", "0")), item_id),
)
approved_order = sorted(approved_ids, key=lambda item_id: (int(source[item_id].get("source_index", "0")), item_id))
review_output = [review_row(item_id, "priority") for item_id in priority_order]
review_output.extend(review_row(item_id, "approved") for item_id in approved_order)
if len(review_output) != expected["human"]:
    raise SystemExit("combined workbook row count drifted")


payload = {
    "schema": SCHEMA,
    "counts": expected,
    "source_tsv": "magica/i18n_audit/release_v26_authority/pass20_remaining_manual_review.tsv",
    "priority_tsv": "magica/i18n_audit/release_v26_authority/pass20_priority_manual_review.tsv",
    "inventory_tsv": "magica/i18n_audit/release_v26_authority/pass20_machine_source_inventory.tsv",
    "shadow_tsv": "magica/i18n_audit/release_v26_authority/pass20_authority_shadowed_machine_items.tsv",
    "authority_resolution_tsv": "magica/i18n_audit/release_v26_authority/pass20_authority_resolutions.tsv",
    "target_manifest": "magica/i18n_audit/release_v26_authority/pass20_product_targets.json",
    "suggested_adoptions_tsv": "magica/i18n_audit/release_v26_authority/pass21_user_directed_suggested_adoptions.tsv",
    "sealed_review": "magica/i18n_audit/release_v26_authority/dsv4_terminal_handoff/full_review.tsv",
    "target_contract_sha256": target_contract_sha256,
    "review_rows": review_output,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"status": "PASS", "output": str(OUT), "counts": expected}, ensure_ascii=False))
