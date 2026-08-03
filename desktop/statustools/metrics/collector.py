"""Facade that gathers every metric into one payload."""

from __future__ import annotations

from . import battery, cpu, disk, memory
from .gpu import GpuReader
from .models import MetricsPayload


class MetricsCollector:
    def __init__(self):
        self._gpu = GpuReader()

    def collect(self) -> MetricsPayload:
        return MetricsPayload(
            cpu=cpu.read(),
            gpu=self._gpu.read(),
            memory=memory.read(),
            disk=disk.read(),
            battery=battery.read(),
        )
