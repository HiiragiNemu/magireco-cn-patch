#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("engine_apply", HERE / "apply-engine-final-root-review.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class EngineApplyTests(unittest.TestCase):
    def make_fixture(self, folder: str):
        base = Path(folder)
        engine = base / "engine_i18n.tsv"
        sidecar = base / "sidecar.json"
        rollback = base / "rollback.json"
        verification = base / "verification.json"
        engine.write_bytes(MODULE.ENGINE.read_bytes())
        sidecar.write_bytes(MODULE.SIDECAR.read_bytes())
        # Tests always begin from the exact pre-application state even when the
        # checked-out product has already received the reviewed corrections.
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        lines = engine.read_text(encoding="utf-8-sig").splitlines()
        for row in payload["rows"]:
            if row["semantic_verdict"] != "correction-proposed":
                continue
            source, _ = lines[row["physical_line"] - 1].split("\t")
            self.assertEqual(source, row["source_key"])
            lines[row["physical_line"] - 1] = f'{source}\t{row["before_cn"]}'
        engine.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
        return engine, sidecar, rollback, verification

    def test_apply_verify_rollback_verify_reapply(self):
        with tempfile.TemporaryDirectory() as folder:
            engine, sidecar, rollback, verification = self.make_fixture(folder)
            before = engine.read_bytes()
            applied = MODULE.apply_review(engine, sidecar, rollback, verification)
            self.assertEqual(applied["status"], "pass")
            self.assertEqual(applied["official_exact_corrections_applied"], 35)
            self.assertEqual(applied["manual_semantic_corrections_applied"], 5)
            self.assertNotEqual(engine.read_bytes(), before)
            self.assertEqual(MODULE.verify_state(engine, sidecar, "applied")["status"], "pass")
            self.assertEqual(MODULE.rollback_review(engine, sidecar, rollback, verification)["status"], "pass")
            self.assertEqual(engine.read_bytes(), before)
            self.assertEqual(MODULE.verify_state(engine, sidecar, "rolled-back")["status"], "pass")
            self.assertEqual(MODULE.apply_review(engine, sidecar, rollback, verification)["status"], "pass")

    def test_source_drift_refuses_without_write(self):
        with tempfile.TemporaryDirectory() as folder:
            engine, sidecar, rollback, verification = self.make_fixture(folder)
            lines = engine.read_text(encoding="utf-8-sig").splitlines()
            lines[1] = "坏源\t否"
            engine.write_text("\n".join(lines) + "\n", encoding="utf-8")
            before = engine.read_bytes()
            with self.assertRaises(ValueError):
                MODULE.apply_review(engine, sidecar, rollback, verification)
            self.assertEqual(engine.read_bytes(), before)

    def test_before_drift_refuses_without_write(self):
        with tempfile.TemporaryDirectory() as folder:
            engine, sidecar, rollback, verification = self.make_fixture(folder)
            lines = engine.read_text(encoding="utf-8-sig").splitlines()
            lines[1] = "いいえ\t坏值"
            engine.write_text("\n".join(lines) + "\n", encoding="utf-8")
            before = engine.read_bytes()
            with self.assertRaises(ValueError):
                MODULE.apply_review(engine, sidecar, rollback, verification)
            self.assertEqual(engine.read_bytes(), before)

    def test_duplicate_sidecar_id_refuses_without_write(self):
        with tempfile.TemporaryDirectory() as folder:
            engine, sidecar, rollback, verification = self.make_fixture(folder)
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            payload["rows"][1]["row_id"] = payload["rows"][0]["row_id"]
            sidecar.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            before = engine.read_bytes()
            with self.assertRaises(ValueError):
                MODULE.apply_review(engine, sidecar, rollback, verification)
            self.assertEqual(engine.read_bytes(), before)

    def test_engine_write_failure_leaves_original(self):
        with tempfile.TemporaryDirectory() as folder:
            engine, sidecar, rollback, verification = self.make_fixture(folder)
            before = engine.read_bytes()
            original = MODULE.atomic_write_bytes

            def fail_engine(path: Path, data: bytes):
                if path == engine:
                    raise OSError("synthetic engine write failure")
                return original(path, data)

            with mock.patch.object(MODULE, "atomic_write_bytes", side_effect=fail_engine):
                with self.assertRaises(OSError):
                    MODULE.apply_review(engine, sidecar, rollback, verification)
            self.assertEqual(engine.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
