from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
OUT = ROOT / "_artifacts/spreadsheet_build/v26_translation_review_1565_input.json"
SCHEMA = "magireco-cn-v26-translation-human-review-workbook/2"


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


def first(mapping: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key, "")
        if value:
            return value
    return ""


source_path = AUDIT / "pass20_remaining_manual_review.tsv"
priority_path = AUDIT / "pass20_priority_manual_review.tsv"
inventory_path = AUDIT / "pass20_machine_source_inventory.tsv"
shadow_path = AUDIT / "pass20_authority_shadowed_machine_items.tsv"
resolution_path = AUDIT / "pass20_authority_resolutions.tsv"
sealed_path = AUDIT / "dsv4_terminal_handoff/full_review.tsv"
target_path = AUDIT / "pass20_product_targets.json"

source_rows = load_tsv(source_path)
priority_rows = load_tsv(priority_path)
inventory_rows = load_tsv(inventory_path)
shadow_rows = load_tsv(shadow_path)
resolution_rows = load_tsv(resolution_path)
sealed_rows = load_tsv(sealed_path)
source = unique(source_rows, "human queue")
priority = unique(priority_rows, "priority queue")
inventory = unique(inventory_rows, "machine inventory")
shadow = unique(shadow_rows, "higher-authority shadow")
resolutions = unique(resolution_rows, "authority resolutions")
sealed = unique(sealed_rows, "sealed review")

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

verdict_labels = {
    "correction": "DS发现错误／建议修正但尚未应用",
    "unresolved": "DS未确定／需人工判断",
    "manual-required": "尚未完成DS审查／需人工判断",
    "approved": "DS已审通过／仍属机器来源，待人工确认",
}


def target_display(target: dict[str, object]) -> tuple[str, str]:
    target_paths = target.get("product_target_paths") or target.get("declared_product_paths") or []
    contexts = target.get("context_snippets") or []
    return (
        "\n".join(str(value) for value in target_paths),
        "\n".join(str(value) for value in contexts).rstrip(" \r\n"),
    )


def review_row(item_id: str, sequence: int, partition: str) -> dict[str, object]:
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
    paths, contexts = target_display(target)
    verdict = row.get("parent_verdict", "")
    if verdict == "approved":
        prefix = "DS审查认为当前译文可接受，但它仍是机器来源；只有人工选择“保留现译”后，才记录为人工已批准。"
    elif verdict == "correction":
        prefix = "DS审查发现当前译文可能有误，请重点核对建议中文和实际上下文。"
    elif verdict == "unresolved":
        prefix = "DS证据不足，请人工结合原文和实际使用位置判断。"
    else:
        prefix = "此前未完成DS审查，请人工直接判断中文语义。"
    rationale = row.get("parent_rationale", "")
    explanation = prefix + (("\n\nDS原始理由：" + rationale) if rationale else "")
    return {
        "sequence": sequence,
        "item_id": item_id,
        "original": original,
        "current_cn": row.get("current_cn", ""),
        "suggested_cn": row.get("suggested_cn", ""),
        "parent_verdict_display": verdict_labels[verdict],
        "review_explanation": explanation,
        "maintenance_layer_type": str(target.get("maintenance_layer_type", "")),
        "maintenance_table": str(target.get("maintenance_table", "")),
        "source_key": row.get("source_key", ""),
        "path_prefix": str(target.get("path_prefix") or "（全局）"),
        "product_target_paths": paths,
        "match_count": int(target.get("match_count", 0)),
        "match_status": str(target.get("match_status", "")),
        "context_snippets": contexts,
        "source_text_sha256": expected_text_hash,
        "source_record_sha256": digest_json(row),
        "target_row_sha256": digest_json(target),
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
priority_output = [review_row(item_id, index, "priority") for index, item_id in enumerate(priority_order, 1)]
approved_output = [review_row(item_id, index, "approved") for index, item_id in enumerate(approved_order, 1)]


def excluded_row(item_id: str, sequence: int, category: str) -> dict[str, object]:
    sealed_row = sealed[item_id]
    metadata = resolutions[item_id] if category == "authority-resolved" else shadow[item_id]
    if category == "authority-resolved":
        reason = "已有官方／Wiki／确认人工等高权威裁决"
        authority_value = metadata.get("final_value", "")
        machine_candidate = sealed_row.get("old_cn", "") or sealed_row.get("current_cn", "")
        authority_tier = metadata.get("authority_tier", "")
        evidence = metadata.get("evidence", "")
    else:
        reason = "机器候选已被更高权威值遮蔽"
        machine_candidate = first(metadata, "machine_candidate", "low_tier_candidate", "candidate_cn") or sealed_row.get("old_cn", "")
        authority_value = first(
            metadata, "authority_value", "selected_value", "effective_cn", "final_value", "protected_authority_text"
        ) or sealed_row.get("protected_authority_text", "") or sealed_row.get("current_cn", "")
        authority_tier = first(metadata, "authority_tier", "selected_authority_tier", "highest_authority_tier")
        evidence = first(metadata, "evidence", "authority_evidence", "selected_authority_evidence")
    payload = {"category": category, "sealed": sealed_row, "metadata": metadata}
    return {
        "sequence": sequence,
        "item_id": item_id,
        "exclusion_reason": reason,
        "original": sealed_row.get("japanese_or_source_original", ""),
        "machine_candidate": machine_candidate,
        "authority_value": authority_value,
        "authority_tier": authority_tier,
        "authority_evidence": evidence,
        "source_location": f"{sealed_row.get('source_path', '')}#{sealed_row.get('source_key', '')}",
        "source_record_sha256": digest_json(sealed_row),
        "excluded_row_sha256": digest_json(payload),
        "excluded_row_json": canonical(payload),
    }


excluded_output = []
for item_id in sorted(resolutions, key=lambda value: (int(sealed[value].get("source_index", "0")), value)):
    excluded_output.append(excluded_row(item_id, len(excluded_output) + 1, "authority-resolved"))
for item_id in sorted(shadow, key=lambda value: (int(sealed[value].get("source_index", "0")), value)):
    excluded_output.append(excluded_row(item_id, len(excluded_output) + 1, "higher-authority-shadowed"))

payload = {
    "schema": SCHEMA,
    "counts": expected,
    "source_tsv": "magica/i18n_audit/release_v26_authority/pass20_remaining_manual_review.tsv",
    "priority_tsv": "magica/i18n_audit/release_v26_authority/pass20_priority_manual_review.tsv",
    "inventory_tsv": "magica/i18n_audit/release_v26_authority/pass20_machine_source_inventory.tsv",
    "shadow_tsv": "magica/i18n_audit/release_v26_authority/pass20_authority_shadowed_machine_items.tsv",
    "target_manifest": "magica/i18n_audit/release_v26_authority/pass20_product_targets.json",
    "sealed_review": "magica/i18n_audit/release_v26_authority/dsv4_terminal_handoff/full_review.tsv",
    "target_contract_sha256": target_contract_sha256,
    "priority_rows": priority_output,
    "approved_rows": approved_output,
    "excluded_rows": excluded_output,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"status": "PASS", "output": str(OUT), "counts": expected}, ensure_ascii=False))
