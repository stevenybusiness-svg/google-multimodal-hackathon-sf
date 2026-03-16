from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
PYTHON = shutil.which("python3.12") or sys.executable


def test_repo_root_smoke_script_runs_cleanly() -> None:
    result = subprocess.run(
        [PYTHON, "scripts/smoke_test.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
