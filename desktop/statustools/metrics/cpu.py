"""CPU usage (psutil) and best-effort CPU temperature.

``psutil.cpu_percent(interval=None)`` is non-blocking and returns the percent
since the previous call, so we prime it once at startup and then rely on the
periodic call cadence (the collector ticks every couple of seconds).

Temperature:
  * Linux  -> ``psutil.sensors_temperatures()`` (coretemp / k10temp / ...).
  * Windows -> WMI ``MSAcpi_ThermalZoneTemperature`` (best-effort; frequently
    requires admin, so it may legitimately read ``None`` -> shown as N/A).
The result is cached because the Windows path spawns a (hidden) subprocess.
"""

from __future__ import annotations

import os
import subprocess
import time

import psutil

from .models import CpuData

_primed = False

_temp_cache: dict = {"ts": 0.0, "val": None}
_TEMP_TTL = 30.0 if os.name == "nt" else 5.0

# Windows: spawn PowerShell without a console window (GUI app), like nvidia-smi.
_WIN_SUBPROCESS_KWARGS = (
    {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    if os.name == "nt"
    else {}
)


def read() -> CpuData:
    global _primed
    if not _primed:
        # Prime the internal counter; the first real value comes next tick.
        psutil.cpu_percent(interval=None)
        _primed = True
        percent = 0.0
    else:
        percent = psutil.cpu_percent(interval=None)
    return CpuData(
        percent=float(percent),
        core_count=psutil.cpu_count() or 1,
        temperature_c=read_cpu_temp(),
    )


def read_cpu_temp() -> float | None:
    now = time.monotonic()
    if (now - _temp_cache["ts"]) < _TEMP_TTL:
        return _temp_cache["val"]

    val = _read_temp_wmi() if os.name == "nt" else _read_temp_psutil()
    _temp_cache["ts"] = now
    _temp_cache["val"] = val
    return val


def _read_temp_psutil() -> float | None:
    """Linux: read hardware sensors via psutil."""
    try:
        temps = psutil.sensors_temperatures()  # type: ignore[attr-defined]
    except Exception:
        return None
    if not temps:
        return None
    # Prefer CPU sensor chips, otherwise take the hottest reading.
    preferred = ("coretemp", "k10temp", "cpu_thermal", "zenpower")
    candidates: list[float] = []
    fallback: list[float] = []
    for chip, entries in temps.items():
        for entry in entries:
            t = getattr(entry, "current", None)
            if t is None:
                continue
            (candidates if chip in preferred else fallback).append(float(t))
    pool = candidates or fallback
    if not pool:
        return None
    return round(max(pool), 1)


def _read_temp_wmi() -> float | None:
    """Windows: thermal zones via WMI. Values are tenths of a degree Kelvin."""
    try:
        cmd = (
            "Get-CimInstance -Namespace root/wmi "
            "-ClassName MSAcpi_ThermalZoneTemperature "
            "| Select-Object -ExpandProperty CurrentTemperature"
        )
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd],
            timeout=6,
            stderr=subprocess.DEVNULL,
            **_WIN_SUBPROCESS_KWARGS,
        )
        text = out.decode(errors="ignore")
        values = [int(x) for x in text.split() if x.lstrip("-").isdigit()]
        if not values:
            return None
        kelvin_tenths = max(values)
        celsius = kelvin_tenths / 10.0 - 273.15
        if 0.0 <= celsius <= 125.0:
            return round(celsius, 1)
        return None
    except Exception:
        return None
