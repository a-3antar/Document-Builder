"""Environment-aware paths (dev and PyInstaller)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from config.constants import APP_DIR_NAME


def resource_root() -> Path:
    """Return the folder that holds bundled resources."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath("resources", *parts)


def _env_dir(var: str, fallback: Path) -> Path:
    base = os.environ.get(var)
    return (Path(base) if base else fallback) / APP_DIR_NAME


def config_dir() -> Path:
    return _env_dir("APPDATA", Path.home() / ".config")


def local_data_dir() -> Path:
    return _env_dir("LOCALAPPDATA", Path.home() / ".local" / "share")


def logs_dir() -> Path:
    return local_data_dir() / "logs"


def temp_dir() -> Path:
    return local_data_dir() / "temp"


def ensure_dirs(*dirs: Path) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
