"""Alert engine: threshold crossings + charging-stall detection, with anti-spam.

Battery alerts are transition-based (fire once when a level is crossed, reset via
hysteresis) so a device hovering at 29% does not spam. Charging-stall re-notifies
on a cooldown while the device stays plugged with no meaningful gain.
"""

from __future__ import annotations

import time

_HYSTERESIS = 3.0        # percent above a threshold before it can re-trigger
_STALL_MIN_GAIN = 1.0    # percent that counts as "battery actually increasing"
_GLOBAL_MIN_GAP = 5.0    # seconds between any two non-critical notifications


class AlertEngine:
    def __init__(self, config, notifier):
        self.config = config
        self.notifier = notifier
        self._names: dict[str, str] = {}
        self._states: dict[str, dict] = {}
        self._last_global_notify = 0.0

    # ---- device lifecycle --------------------------------------------------
    def on_device_connected(self, device_id: str, name: str) -> None:
        self._names[device_id] = name
        self._states.setdefault(device_id, self._fresh_state())

    def on_device_disconnected(self, device_id: str) -> None:
        self._states.pop(device_id, None)

    def device_name(self, device_id: str) -> str:
        return self._names.get(device_id, device_id)

    @staticmethod
    def _fresh_state() -> dict:
        return {
            "low_alerted": False,
            "critical_alerted": False,
            "plugged_at": None,
            "baseline_percent": None,
            "stall_notified_at": None,
        }

    # ---- entry point -------------------------------------------------------
    def on_metrics(self, device_id: str, data: dict) -> None:
        if not isinstance(data, dict):
            return
        self._states.setdefault(device_id, self._fresh_state())
        battery = data.get("battery") or {}
        if battery.get("present"):
            self._eval_battery(device_id, battery, time.time())

    # ---- battery thresholds + charging stall -------------------------------
    def _eval_battery(self, device_id: str, battery: dict, now: float) -> None:
        percent = battery.get("percent")
        plugged = bool(battery.get("plugged"))
        if percent is None:
            return
        percent = float(percent)
        st = self._states[device_id]
        th = self.config.thresholds

        # Critical level (bypasses cooldown).
        if percent <= th.battery_critical_percent:
            if not st["critical_alerted"]:
                self._notify(
                    device_id, "battery_critical",
                    f"{self._name(device_id)} 电量危急：{percent:.0f}%",
                    critical=True, now=now,
                )
                st["critical_alerted"] = True
                st["low_alerted"] = True
        elif percent <= th.battery_low_percent:
            if not st["low_alerted"]:
                self._notify(
                    device_id, "battery_low",
                    f"{self._name(device_id)} 电量偏低：{percent:.0f}%（阈值 {th.battery_low_percent}%）",
                    critical=False, now=now,
                )
                st["low_alerted"] = True

        # Hysteresis resets so the alerts can fire again on the next drop.
        if percent > th.battery_critical_percent + _HYSTERESIS:
            st["critical_alerted"] = False
        if percent > th.battery_low_percent + _HYSTERESIS:
            st["low_alerted"] = False

        self._eval_charging_stall(device_id, percent, plugged, now, st)

    def _eval_charging_stall(self, device_id: str, percent: float,
                             plugged: bool, now: float, st: dict) -> None:
        if not plugged:
            st["plugged_at"] = None
            st["baseline_percent"] = None
            st["stall_notified_at"] = None
            return

        if st["plugged_at"] is None:
            # Just plugged in: record baseline and start the clock.
            st["plugged_at"] = now
            st["baseline_percent"] = percent
            st["stall_notified_at"] = None
            return

        elapsed_min = (now - st["plugged_at"]) / 60.0
        if elapsed_min < self.config.charging_stall_minutes:
            return

        gain = percent - (st["baseline_percent"] or percent)
        if gain < _STALL_MIN_GAIN:
            # Stalled: notify, then respect the cooldown before re-notifying.
            last = st["stall_notified_at"]
            cooldown = self.config.notification_cooldown_seconds
            if last is None or (now - last) >= cooldown:
                self._notify(
                    device_id, "charging_stall",
                    f"{self._name(device_id)} 已插电约 {elapsed_min:.0f} 分钟，"
                    f"电量仍为 {percent:.0f}%（未见增长）。请检查充电器/数据线。",
                    critical=False, now=now,
                )
                st["stall_notified_at"] = now
        else:
            # Charging is progressing: advance the baseline and restart the clock.
            st["baseline_percent"] = percent
            st["plugged_at"] = now
            st["stall_notified_at"] = None

    # ---- delivery ----------------------------------------------------------
    def _notify(self, device_id: str, key: str, message: str,
                critical: bool, now: float) -> None:
        if not critical and (now - self._last_global_notify) < _GLOBAL_MIN_GAP:
            return
        self._last_global_notify = now
        self.notifier.notify("Status Tools", message, warning=True)

    def _name(self, device_id: str) -> str:
        return self._names.get(device_id, device_id)
