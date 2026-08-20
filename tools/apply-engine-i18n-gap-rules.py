#!/usr/bin/env python3
"""Apply, verify, or roll back the bounded native AP-popup rules.

The current legacy-client consumer supports exact and ``^`` prefix rules but
not substring rules.  The native AP timer is one label with a variable final
countdown, so this tool materializes the complete, finite 0:00..5:00 value set
of the *first* countdown as ordered prefixes.  Each rule consumes both English
labels and preserves only the variable full-recovery countdown suffix.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TABLE = REPO / "madomagi" / "engine_i18n.tsv"
REPORT = (
    REPO
    / "magica"
    / "research"
    / "totentanz-full-localization-20260817"
    / "engine-i18n"
    / "ap-recovery-gap-verification.json"
)

EXPECTED_BASE_LOGICAL_RULES = 314
EXPECTED_BASE_PHYSICAL_LINES = 315
TIMER_MIN_SECONDS = 0
TIMER_MAX_SECONDS = 5 * 60
EXPECTED_TIMER_RULES = TIMER_MAX_SECONDS - TIMER_MIN_SECONDS + 1
EXPECTED_ACTIVE_LOGICAL_RULES = EXPECTED_BASE_LOGICAL_RULES + EXPECTED_TIMER_RULES
EXPECTED_ACTIVE_PHYSICAL_LINES = EXPECTED_BASE_PHYSICAL_LINES + EXPECTED_TIMER_RULES


STATIC_RULES = [
    ("ENGINE-AP-ITEM-001", "exact", "50 AP Potion", "AP回复药50", "official-cn", "A:/magicaOLD official item name"),
    ("ENGINE-AP-ITEM-002", "exact", "AP Potion", "AP回复药", "official-cn", "A:/magicaOLD official item name"),
    ("ENGINE-AP-ITEM-003", "exact", "Magia Stones", "魔法石", "official-cn", "A:/magicaOLD official item name"),
    ("ENGINE-AP-ACTION-001", "prefix", "Use ", "消费 ", "official-cn", "A:/magicaOLD/template/user/APPopup.html"),
    ("ENGINE-AP-COUNT-001", "prefix", "Stock: ", "持有数 ", "official-cn", "A:/magicaOLD/template/user/APPopup.html"),
    ("ENGINE-AP-COST-001", "prefix", "Cost: ", "消费 ", "official-cn", "A:/magicaOLD/template/user/APPopup.html"),
    ("ENGINE-AP-ACTION-002", "exact", "Restore", "回复", "official-cn", "A:/magicaOLD/template/user/APPopup.html"),
]


def timer_text(total_seconds: int) -> str:
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def build_timer_rules() -> list[tuple[str, str, str, str, str, str]]:
    rules = []
    for total_seconds in range(TIMER_MIN_SECONDS, TIMER_MAX_SECONDS + 1):
        timer = timer_text(total_seconds)
        rules.append(
            (
                f"ENGINE-AP-DYNAMIC-TIMER-{total_seconds:03d}",
                "prefix",
                f"1 AP will recover in {timer} / AP will be fully recovered in ",
                f"距回复1 AP还有 {timer} / 距AP全部回复还有 ",
                "confirmed-human",
                "A:/magicaOLD/template/user/APPopup.html; native AP label shape from runtime screenshot; "
                "legacy consumer exact/^prefix contract",
            )
        )
    return rules


TIMER_RULES = build_timer_rules()
RULES = STATIC_RULES + TIMER_RULES

UNSUPPORTED_RULES = [
    (
        "ENGINE-AP-TIMER-001",
        "substring",
        " AP will recover in ",
        " AP恢复倒计时：",
        "removed-unsupported",
        "current legacy-client main consumer has no substring-rule support",
    ),
    (
        "ENGINE-AP-TIMER-002",
        "substring",
        " / AP will be fully recovered in ",
        " / AP全满倒计时：",
        "removed-unsupported",
        "current legacy-client main consumer has no substring-rule support",
    ),
]


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")


def rendered_rule(rule: tuple[str, str, str, str, str, str]) -> str:
    _, kind, source, target, _, _ = rule
    return {"exact": "", "prefix": "^", "substring": "~"}[kind] + escape(source) + "\t" + escape(target)


def semantic_key(line: str) -> tuple[str, str] | None:
    if not line or line.startswith("#") or "\t" not in line:
        return None
    left = line.split("\t", 1)[0]
    if left.startswith("^"):
        return "prefix", left[1:]
    if left.startswith("~"):
        return "substring", left[1:]
    return "exact", left


def atomic_write(path: Path, raw: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def inspect(text: str, rules: list[tuple[str, str, str, str, str, str]]) -> list[dict]:
    lines = text.splitlines()
    by_key: dict[tuple[str, str], list[str]] = {}
    for line in lines:
        key = semantic_key(line)
        if key:
            by_key.setdefault(key, []).append(line)
    records = []
    for rule in rules:
        item_id, kind, source, target, source_tier, evidence = rule
        rendered = rendered_rule(rule)
        key = semantic_key(rendered)
        assert key is not None
        records.append(
            {
                "rule_id": item_id,
                "kind": kind,
                "source": source,
                "target": target,
                "source_tier": source_tier,
                "evidence": evidence,
                "rendered": rendered,
                "matching_source_rules": by_key.get(key, []),
                "exact_line_count": lines.count(rendered),
                "runtime_contract": (
                    "unsupported-by-current-main-and-removed-from-runtime-table"
                    if kind == "substring"
                    else "supported-by-current-main-exact-or-prefix"
                ),
            }
        )
    return records


def require_state(records: list[dict], present: bool) -> None:
    for rec in records:
        found = rec["matching_source_rules"]
        if present:
            if found != [rec["rendered"]] or rec["exact_line_count"] != 1:
                raise ValueError(f"{rec['rule_id']} missing, duplicated, or drifted: {found!r}")
        elif found:
            raise ValueError(f"{rec['rule_id']} present, duplicated, or conflicted: {found!r}")


def table_shape(text: str) -> tuple[int, int]:
    physical = len(text.splitlines())
    logical = 0
    keys: list[tuple[str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        key = semantic_key(line)
        if key is None:
            raise ValueError(f"malformed engine rule at physical line {number}")
        logical += 1
        keys.append(key)
    duplicates = [key for key, count in Counter(keys).items() if count != 1]
    if duplicates:
        raise ValueError(f"duplicate engine source keys: {duplicates!r}")
    return logical, physical


def require_shape(text: str, logical: int, physical: int, label: str) -> None:
    actual = table_shape(text)
    expected = (logical, physical)
    if actual != expected:
        raise ValueError(f"{label} engine shape drifted: actual={actual!r}, expected={expected!r}")


def newline_style(text: str) -> str:
    without_crlf = text.replace("\r\n", "")
    if "\r" in without_crlf or ("\r\n" in text and "\n" in without_crlf):
        raise ValueError("engine table has mixed or unsupported line endings")
    return "\r\n" if "\r\n" in text else "\n"


def remove_owned_lines(text: str, owned: set[str]) -> tuple[str, list[str]]:
    kept: list[str] = []
    removed: list[str] = []
    for chunk in text.splitlines(keepends=True):
        line = chunk.rstrip("\r\n")
        if line in owned:
            removed.append(line)
        else:
            kept.append(chunk)
    return "".join(kept), removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check-before", "apply", "verify", "rollback"))
    parser.add_argument("--table", type=Path, default=TABLE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    table = args.table.resolve()
    raw = table.read_bytes()
    if b"\x00" in raw:
        raise ValueError("engine table contains NUL")
    text = raw.decode("utf-8")
    newline = newline_style(text)
    if not text.endswith(newline):
        raise ValueError("engine table must end with its established newline")

    static_before = inspect(text, STATIC_RULES)
    timer_before = inspect(text, TIMER_RULES)
    unsupported_before = inspect(text, UNSUPPORTED_RULES)
    require_state(unsupported_before, False)
    require_state(static_before, True)
    before_shape = (
        EXPECTED_ACTIVE_LOGICAL_RULES,
        EXPECTED_ACTIVE_PHYSICAL_LINES,
    ) if args.mode in {"verify", "rollback"} else (
        EXPECTED_BASE_LOGICAL_RULES,
        EXPECTED_BASE_PHYSICAL_LINES,
    )
    require_state(timer_before, args.mode in {"verify", "rollback"})
    require_shape(text, *before_shape, label="pre-operation")

    unrelated_content_preserved = True
    if args.mode == "apply":
        appended = newline.join(rendered_rule(rule) for rule in TIMER_RULES) + newline
        updated = text + appended
        if not updated.startswith(text):
            raise AssertionError("apply changed pre-existing engine bytes")
        atomic_write(table, updated.encode("utf-8"))
    elif args.mode == "rollback":
        owned = {rendered_rule(rule) for rule in TIMER_RULES}
        updated, removed = remove_owned_lines(text, owned)
        if Counter(removed) != Counter(owned):
            raise ValueError(f"rollback ownership set drifted: {removed!r}")
        expected_unrelated, _ = remove_owned_lines(text, owned)
        unrelated_content_preserved = updated == expected_unrelated
        if not unrelated_content_preserved:
            raise AssertionError("rollback changed unrelated engine content")
        atomic_write(table, updated.encode("utf-8"))

    final_raw = table.read_bytes()
    final_text = final_raw.decode("utf-8")
    static_records = inspect(final_text, STATIC_RULES)
    timer_records = inspect(final_text, TIMER_RULES)
    unsupported_records = inspect(final_text, UNSUPPORTED_RULES)
    active_present = args.mode in {"apply", "verify"}
    require_state(static_records, True)
    require_state(timer_records, active_present)
    require_state(unsupported_records, False)
    final_shape = (
        EXPECTED_ACTIVE_LOGICAL_RULES,
        EXPECTED_ACTIVE_PHYSICAL_LINES,
    ) if active_present else (
        EXPECTED_BASE_LOGICAL_RULES,
        EXPECTED_BASE_PHYSICAL_LINES,
    )
    require_shape(final_text, *final_shape, label="post-operation")

    logical_rules, physical_lines = table_shape(final_text)
    report = {
        "ok": True,
        # Keep the persisted evidence independent of whether it was refreshed by
        # apply or by a later read-only verification.  Consumers bind to this
        # runtime contract; ``operation`` records how the evidence was produced.
        "mode": "current-main-compatible",
        "operation": args.mode,
        "active_rules": len(STATIC_RULES) + (len(TIMER_RULES) if active_present else 0),
        "rules": len(RULES),
        "exact": sum(rule[1] == "exact" for rule in RULES),
        "prefix": sum(rule[1] == "prefix" for rule in RULES),
        "substring": 0,
        "baseline_rules": EXPECTED_BASE_LOGICAL_RULES,
        "generated_timer_rules": EXPECTED_TIMER_RULES,
        "unsupported_rules": len(UNSUPPORTED_RULES),
        "unsupported_present": sum(bool(rec["matching_source_rules"]) for rec in unsupported_records),
        "logical_rule_count": logical_rules,
        "final_engine_rule_count": logical_rules,
        "physical_line_count": physical_lines,
        "line_count": physical_lines,
        "unrelated_content_preserved": unrelated_content_preserved,
        "consumer_requirement": "current legacy-client main: exact and ^prefix only; dynamic AP timer closed by finite prefix expansion",
        "timer_coverage": {
            "first_countdown_min_seconds": TIMER_MIN_SECONDS,
            "first_countdown_max_seconds": TIMER_MAX_SECONDS,
            "value_count": EXPECTED_TIMER_RULES,
            "source_shape": "1 AP will recover in M:SS / AP will be fully recovered in <variable>",
            "target_shape": "距回复1 AP还有 M:SS / 距AP全部回复还有 <variable>",
            "all_values_present": active_present,
            "samples": [
                timer_records[0],
                timer_records[154],
                timer_records[-1],
            ],
        },
        "records": static_records + (timer_records if active_present else []),
        "unsupported_records": unsupported_records,
        "removed_unsupported_records": unsupported_records,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.mode in {"apply", "verify"}:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
