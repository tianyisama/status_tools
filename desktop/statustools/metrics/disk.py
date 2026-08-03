"""System-disk usage via psutil."""

from __future__ import annotations

import psutil

from ..platform_utils import system_drive_root
from .models import DiskData

_GB = 1024 ** 3


def read() -> DiskData:
    du = psutil.disk_usage(system_drive_root())
    return DiskData(
        percent=float(du.percent),
        used_gb=du.used / _GB,
        total_gb=du.total / _GB,
    )
