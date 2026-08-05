"""Dataclasses shared by the metric readers and the wire protocol.

These mirror `protocol/schema.json`. Fields that cannot be read on a given
platform are set to ``None`` (never omitted) so every peer sees the same shape.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class CpuData:
    percent: float
    core_count: int
    temperature_c: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "percent": round(self.percent, 1),
            "core_count": self.core_count,
            "temperature_c": self.temperature_c,
        }


@dataclass
class GpuData:
    available: bool
    percent: Optional[float] = None
    memory_used_mb: Optional[int] = None
    memory_total_mb: Optional[int] = None
    temperature_c: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "percent": None if self.percent is None else round(self.percent, 1),
            "memory_used_mb": self.memory_used_mb,
            "memory_total_mb": self.memory_total_mb,
            "temperature_c": self.temperature_c,
        }


@dataclass
class MemoryData:
    percent: float
    used_mb: int
    total_mb: int

    def to_dict(self) -> dict:
        return {
            "percent": round(self.percent, 1),
            "used_mb": self.used_mb,
            "total_mb": self.total_mb,
        }


@dataclass
class DiskData:
    percent: float
    used_gb: float
    total_gb: float

    def to_dict(self) -> dict:
        return {
            "percent": round(self.percent, 1),
            "used_gb": round(self.used_gb, 1),
            "total_gb": round(self.total_gb, 1),
        }


@dataclass
class BatteryData:
    present: bool
    percent: Optional[float] = None
    plugged: Optional[bool] = None
    # "charging" | "discharging" | "full" | "no_battery" | "unknown"
    status: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "present": self.present,
            "percent": None if self.percent is None else round(self.percent, 1),
            "plugged": self.plugged,
            "status": self.status,
        }


@dataclass
class MetricsPayload:
    cpu: CpuData
    gpu: GpuData
    memory: MemoryData
    disk: DiskData
    battery: BatteryData

    def to_protocol_dict(self) -> dict:
        """The `data` field of a `metrics` message (see protocol/SPEC.md)."""
        return {
            "cpu": self.cpu.to_dict(),
            "gpu": self.gpu.to_dict(),
            "memory": self.memory.to_dict(),
            "disk": self.disk.to_dict(),
            "battery": self.battery.to_dict(),
        }
