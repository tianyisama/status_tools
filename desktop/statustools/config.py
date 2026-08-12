"""Persistent settings, stored as JSON in the per-user data dir."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional

from .platform_utils import config_path


@dataclass
class AlertThresholds:
    battery_low_percent: int = 30
    battery_critical_percent: int = 15
    cpu_high_percent: int = 95
    memory_high_percent: int = 90
    disk_high_percent: int = 90


@dataclass
class Config:
    # Networking
    service_port: int = 9700
    discovery_port: int = 9701
    server_enabled: bool = True

    # Appearance / behaviour
    update_interval_seconds: float = 2.0
    widget_opacity: float = 0.62        # clear-glass body transparency
    widget_x: Optional[int] = None
    widget_y: Optional[int] = None
    embed_desktop: bool = True          # try desktop embedding (Phase 2)
    acrylic: bool = False               # Windows frosted-glass (acrylic) backdrop
    # "auto" follows the desktop wallpaper luminance; "dark"/"light" override.
    theme_mode: str = "auto"

    # Alerts
    thresholds: AlertThresholds = field(default_factory=AlertThresholds)
    charging_stall_minutes: int = 10
    notification_cooldown_seconds: int = 300

    # ---- (de)serialisation ----
    @staticmethod
    def load() -> "Config":
        cfg = Config()
        path = config_path()
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                # Migrate the old defaults (saved on every run before the
                # clear-glass look): opaque body + acrylic caused black
                # corners behind the rounded glass.
                if raw.get("widget_opacity") == 0.9:
                    raw["widget_opacity"] = Config.widget_opacity
                if raw.get("acrylic") is True:
                    raw["acrylic"] = Config.acrylic
                cfg._merge(raw)
            except Exception:
                pass  # corrupted config -> fall back to defaults
        return cfg

    def save(self) -> None:
        try:
            config_path().write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _merge(self, raw: dict) -> None:
        th = raw.pop("thresholds", None)
        for key, value in raw.items():
            if hasattr(self, key):
                setattr(self, key, value)
        if isinstance(th, dict):
            for key, value in th.items():
                if hasattr(self.thresholds, key):
                    setattr(self.thresholds, key, value)
