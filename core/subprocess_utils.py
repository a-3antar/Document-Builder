"""Quiet subprocess helper (no console window on Windows)."""
from __future__ import annotations

import subprocess
from typing import Sequence


def run_quiet(args: Sequence[object], timeout: float = 30) -> subprocess.CompletedProcess[str]:
    """Run a command, capture UTF-8 output, never flash a console window."""
    return subprocess.run(
        [str(a) for a in args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))