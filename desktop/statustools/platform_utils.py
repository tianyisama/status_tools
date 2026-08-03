"""OS detection and well-known paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_windows() -> bool:
    return os.name == "nt"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_wayland() -> bool:
    """True when the Linux session is Wayland (desktop embedding is limited there)."""
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def data_dir() -> Path:
    """Per-user config/data directory, created on demand."""
    if is_windows():
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        d = base / "StatusTools"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        d = base / "statustools"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return data_dir() / "config.json"


def alert_log_path() -> Path:
    return data_dir() / "alerts.log"


def system_drive_root() -> str:
    """Root path of the system disk (for disk usage)."""
    if is_windows():
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"
