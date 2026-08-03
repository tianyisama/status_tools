"""Battery status via psutil.

``psutil.sensors_battery()`` returns ``None`` on machines without a battery
(most desktops) -> we report ``present=False`` so the UI shows a plug icon.
"""

from __future__ import annotations

import psutil

from .models import BatteryData


def read() -> BatteryData:
    sb = psutil.sensors_battery()
    if sb is None:
        return BatteryData(present=False, percent=None, plugged=None, status="no_battery")

    percent = float(sb.percent)
    plugged = bool(sb.power_plugged)
    if plugged:
        status = "full" if percent >= 99.5 else "charging"
    else:
        status = "discharging"
    return BatteryData(present=True, percent=percent, plugged=plugged, status=status)
