"""GPU usage, best-effort.

NVIDIA cards are read via ``nvidia-smi`` (bundled with the driver). Anything
else (AMD / integrated / no driver) reports ``available=False`` so the UI shows
N/A. Reading is cached briefly because spawning a subprocess is comparatively
expensive and the widget ticks every couple of seconds. Never raises.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

from .models import GpuData

# On Windows a GUI (console-less) process spawning a console app like nvidia-smi
# would otherwise flash a visible console window on every poll. CREATE_NO_WINDOW
# suppresses that. See bug: "CMD window keeps flashing".
if os.name == "nt":
    _SUBPROCESS_KWARGS = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
else:
    _SUBPROCESS_KWARGS = {}

_QUERY = (
    "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu"
)
_FORMAT = "--format=csv,noheader,nounits"
_NOT_READABLE = {"[N/A]", "[Not Supported]", ""}


class GpuReader:
    def __init__(self, cache_ttl: float = 1.5):
        self._nvidia_smi = shutil.which("nvidia-smi")
        self._cache_ttl = cache_ttl
        self._last_ts = 0.0
        self._last: GpuData | None = None

    def read(self) -> GpuData:
        now = time.monotonic()
        if self._last is not None and (now - self._last_ts) < self._cache_ttl:
            return self._last

        if not self._nvidia_smi:
            result = GpuData(available=False)
        else:
            result = self._read_nvidia()

        self._last = result
        self._last_ts = now
        return result

    def _read_nvidia(self) -> GpuData:
        try:
            out = subprocess.check_output(
                [self._nvidia_smi, _QUERY, _FORMAT],
                timeout=3,
                stderr=subprocess.DEVNULL,
                **_SUBPROCESS_KWARGS,
            )
            first_line = out.decode(errors="replace").strip().splitlines()[0]
            fields = [f.strip() for f in first_line.split(",")]
            if len(fields) < 4 or any(f in _NOT_READABLE for f in fields):
                return GpuData(available=False)
            return GpuData(
                available=True,
                percent=float(fields[0]),
                memory_used_mb=int(float(fields[1])),
                memory_total_mb=int(float(fields[2])),
                temperature_c=float(fields[3]),
            )
        except Exception:
            return GpuData(available=False)
