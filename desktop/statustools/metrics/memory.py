"""Memory usage via psutil."""

from __future__ import annotations

import psutil

from .models import MemoryData

_MB = 1024 * 1024


def read() -> MemoryData:
    vm = psutil.virtual_memory()
    return MemoryData(
        percent=float(vm.percent),
        used_mb=int(vm.used // _MB),
        total_mb=int(vm.total // _MB),
    )
