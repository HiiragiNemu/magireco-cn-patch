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
    working_tree_bytes = ENGINE.read_bytes()
    assert not working_tree_bytes.startswith(b"\xef\xbb\xbf")
    product_bytes = working_tree_bytes.replace(b"\r\n", b"\n")
    assert b"\r" not in product_bytes
    with tempfile.TemporaryDirectory() as temp_raw:
        temp = Path(temp_raw)
        rolled_back = temp / "rolled-back.tsv"
        applied = temp / "applied.tsv"
        current = temp / "current.tsv"
        current.write_bytes(product_bytes)

        header, product_pairs = module.load_engine(current)
        assert len(product_pairs) == 702
        official_core = product_pairs[:621]
        extension = product_pairs[621:]
        assert len(extension) == 81
        assert len({source for source, _ in official_core}) == 621
        assert len({source for source, _ in extension}) == 81
        assert not ({source for source, _ in official_core} & {source for source, _ in extension})

        rollback_bytes, rollback_report = module.transform(current, EVIDENCE, "rollback")
        rolled_back.write_bytes(rollback_bytes)
        assert rollback_report["input_logical_rules"] == 702
        assert rollback_report["output_logical_rules"] == 696
        assert rollback_report["official_core_logical_rules"] == 621
        assert rollback_report["protected_extension_logical_rules"] == 81
        assert rollback_report["changed_records"] == 85

        _, rollback_pairs = module.load_engine(rolled_back)
        assert rollback_pairs[615:] == extension

        applied_bytes, apply_report = module.transform(rolled_back, EVIDENCE, "apply")
        applied.write_bytes(applied_bytes)
        assert apply_report["input_logical_rules"] == 696
        assert apply_report["output_logical_rules"] == 702
        assert apply_report["official_core_logical_rules"] == 615
        assert apply_report["protected_extension_logical_rules"] == 81
        assert apply_report["changed_records"] == 85
        assert applied_bytes == product_bytes

        _, applied_pairs = module.load_engine(applied)
        assert applied_pairs[621:] == extension

        drifted = temp / "drifted.tsv"
        text = rollback_bytes.decode("utf-8")
        drifted.write_text(text.replace("スキル使用\t使用技能", "スキル使用\t漂移", 1), encoding="utf-8", newline="\n")
        try:
            module.transform(drifted, EVIDENCE, "apply")
        except AssertionError as exc:
            assert "before-value drift" in str(exc)
        else:
            raise AssertionError("before-value drift was not rejected")

    assert ENGINE.read_bytes() == working_tree_bytes

    print("PASS: official CN native engine 621-core + 81-extension apply/rollback/drift gates")


if __name__ == "__main__":
    main()
