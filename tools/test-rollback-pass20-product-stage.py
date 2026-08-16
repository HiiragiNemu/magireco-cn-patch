#!/usr/bin/env python3

from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_tool():
    path = ROOT / "tools/rollback-pass20-product-stage.py"
    spec = importlib.util.spec_from_file_location("pass20_rollback_tested", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


def fixture(root: Path) -> tuple[Path, Path, Path]:
    stage = root / "relocated-stage"
    product = root / "separate-product"
    rel = "magica/js/example.js"
    before = b"const value = 'before';\n"
    after = b"const value = 'after';\n"
    before_path = stage / "rollback/before" / rel
    after_path = stage / "rollback/after" / rel
    current_path = product / rel
    for path, data in ((before_path, before), (after_path, after), (current_path, after)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    payload = {
        "schema": "magireco-cn-pass20-product-rollback/1",
        "files": [{
            "path": rel,
            "before_snapshot": f"rollback/before/{rel}",
            "after_snapshot": f"rollback/after/{rel}",
            "before_sha256": sha256(before).hexdigest(),
            "after_sha256": sha256(after).hexdigest(),
            "before_size": len(before),
            "after_size": len(after),
        }],
    }
    manifest = stage / "rollback/rollback.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
    return stage, product, current_path


class Pass20RollbackTests(unittest.TestCase):
    def test_01_relocated_stage_rolls_back_exact_bytes(self):
        with tempfile.TemporaryDirectory(prefix="pass20-rollback-") as temp:
            stage, product, current = fixture(Path(temp))
            result = TOOL.rollback(stage, product)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["restored_files"], 1)
            self.assertEqual(current.read_bytes(), b"const value = 'before';\n")

    def test_02_backslash_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="pass20-rollback-") as temp:
            with self.assertRaisesRegex(TOOL.RollbackError, "unsafe rollback product path"):
                TOOL.safe_join(Path(temp), "magica/..\\outside.txt")

    def test_03_snapshot_digest_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="pass20-rollback-") as temp:
            stage, product, _current = fixture(Path(temp))
            (stage / "rollback/before/magica/js/example.js").write_bytes(b"tampered\n")
            with self.assertRaisesRegex(TOOL.RollbackError, "before snapshot digest or size drifted"):
                TOOL.rollback(stage, product)

    def test_04_duplicate_product_path_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="pass20-rollback-") as temp:
            stage, product, _current = fixture(Path(temp))
            manifest = stage / "rollback/rollback.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["files"].append(dict(payload["files"][0]))
            manifest.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(TOOL.RollbackError, "duplicate or invalid"):
                TOOL.rollback(stage, product)


if __name__ == "__main__":
    unittest.main(verbosity=2)
