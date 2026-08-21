#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools/apply-official-cn-native-engine.py"
EVIDENCE = (
    ROOT
    / "magica/research/totentanz-full-localization-20260817/engine-i18n"
    / "official-cn-native-exhaustion-20260821/official-cn-native-localization-exhaustion.json"
)
ENGINE = ROOT / "madomagi/engine_i18n.tsv"

spec = importlib.util.spec_from_file_location("native_engine_apply", TOOL)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def main() -> None:
    product_bytes = ENGINE.read_bytes()
    with tempfile.TemporaryDirectory() as temp_raw:
        temp = Path(temp_raw)
        baseline = temp / "baseline.tsv"
        applied = temp / "applied.tsv"
        current = temp / "current.tsv"
        current.write_bytes(product_bytes)

        logical_rules = sum("\t" in line for line in product_bytes.decode("utf-8").splitlines())
        if logical_rules == 621:
            baseline_bytes, initial_rollback = module.transform(current, EVIDENCE, "rollback")
            assert initial_rollback["changed_records"] == 85
        elif logical_rules == 615:
            baseline_bytes = product_bytes
        else:
            raise AssertionError(f"unexpected product engine row count: {logical_rules}")
        baseline.write_bytes(baseline_bytes)

        applied_bytes, apply_report = module.transform(baseline, EVIDENCE, "apply")
        applied.write_bytes(applied_bytes)
        assert apply_report["input_logical_rules"] == 615
        assert apply_report["output_logical_rules"] == 621
        assert apply_report["changed_records"] == 85

        rollback_bytes, rollback_report = module.transform(applied, EVIDENCE, "rollback")
        assert rollback_report["input_logical_rules"] == 621
        assert rollback_report["output_logical_rules"] == 615
        assert rollback_bytes == baseline_bytes

        drifted = temp / "drifted.tsv"
        text = baseline_bytes.decode("utf-8")
        drifted.write_text(text.replace("スキル使用\t使用技能", "スキル使用\t漂移", 1), encoding="utf-8", newline="\n")
        try:
            module.transform(drifted, EVIDENCE, "apply")
        except AssertionError as exc:
            assert "before-value drift" in str(exc)
        else:
            raise AssertionError("before-value drift was not rejected")

    assert ENGINE.read_bytes() == product_bytes

    print("PASS: official CN native engine apply/rollback/drift gates")


if __name__ == "__main__":
    main()
