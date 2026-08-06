from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent


def compare_tree(left: Path, right: Path, relative_paths: list[str]) -> bool:
    return all((left / rel).read_bytes() == (right / rel).read_bytes() for rel in relative_paths)


def run_git(arguments: list[str], cwd: Path) -> None:
    run = subprocess.run(
        ["git", "-c", "core.autocrlf=false", *arguments],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    if run.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed ({run.returncode})\nstdout={run.stdout}\nstderr={run.stderr}"
        )


def main() -> None:
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    relative_paths = [entry["path"] for entry in manifest["files"]]
    stage = HERE / "verification_patch_stage"
    resolved = stage.resolve()
    if HERE.resolve() not in resolved.parents:
        raise RuntimeError(f"invalid verification stage: {resolved}")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copytree(HERE / "baseline", stage / "magica")
    patch = HERE / "new_ui_localization.patch"

    run_git(["apply", "--check", str(patch)], stage)
    run_git(["apply", str(patch)], stage)
    if not compare_tree(stage / "magica", HERE / "overlay", relative_paths):
        raise AssertionError("patch application output does not match overlay")

    run_git(["apply", "-R", "--check", str(patch)], stage)
    run_git(["apply", "-R", str(patch)], stage)
    if not compare_tree(stage / "magica", HERE / "baseline", relative_paths):
        raise AssertionError("reverse patch output does not match baseline")

    print(
        f"PATCH_ROUNDTRIP_OK files={len(relative_paths)} "
        f"apply_match={len(relative_paths)}/{len(relative_paths)} "
        f"rollback_match={len(relative_paths)}/{len(relative_paths)}"
    )


if __name__ == "__main__":
    main()
