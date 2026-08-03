"""CPU usage via psutil.

``psutil.cpu_percent(interval=None)`` is non-blocking and returns the percent
since the previous call, so we prime it once at startup and then rely on the
periodic call cadence (the collector ticks every couple of seconds).
"""

from __future__ import annotations

import psutil

from .models import CpuData

_primed = False


def read() -> CpuData:
    global _primed
    if not _primed:
        # Prime the internal counter; the first real value comes next tick.
        psutil.cpu_percent(interval=None)
        _primed = True
        percent = 0.0
    else:
        percent = psutil.cpu_percent(interval=None)
    return CpuData(percent=float(percent), core_count=psutil.cpu_count() or 1)
