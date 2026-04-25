"""Backward-compatibility meta-test (T019).

The faithful-port surface (the 13 stage modules, 142+ tests) is
unchanged by the v1 Pythonic layer. This meta-test asserts pytest can
still collect at least 142 tests across the suite — a structural guard
against accidental removal of faithful-port test files.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_collected_tests_at_or_above_baseline():
    """`pytest --collect-only -q` collects ≥ 142 tests."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Exit code 0 even when collection only.
    assert result.returncode == 0, result.stdout + result.stderr
    # The tail line of `-q` collect-only is "<N>/<M> tests collected" or
    # "<N> tests collected"; parse the first int we find on it.
    tail_lines = [
        ln for ln in result.stdout.strip().splitlines() if "test" in ln
    ]
    assert tail_lines, f"could not parse collect output:\n{result.stdout}"
    summary = tail_lines[-1]
    n_collected = int(summary.split()[0])
    assert n_collected >= 142, (
        f"expected ≥ 142 collected tests, got {n_collected}\n{summary}"
    )
