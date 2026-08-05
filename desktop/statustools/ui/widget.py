"""The frameless, translucent, draggable desktop widget.

It is *not* always-on-top: it uses ``WindowStaysOnBottomHint`` in fallback mode
and (optionally, Phase 2) gets re-parented into the desktop layer via WorkerW.
Metric collection happens on a worker ``QThread`` so the UI never blocks on the
``nvidia-smi`` subprocess.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QRectF, Signal, QThread
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..metrics.collector import MetricsCollector
from ..metrics.models import MetricsPayload

# ---- palette ---------------------------------------------------------------
BG = QColor(18, 18, 24)
BORDER = QColor(255, 255, 255, 26)
FG = QColor(235, 236, 240)
FG_DIM = QColor(150, 152, 160)
TRACK = QColor(255, 255, 255, 22)
GREEN = QColor(76, 217, 123)
YELLOW = QColor(255, 180, 84)
RED = QColor(255, 92, 92)
ACCENT = QColor(96, 150, 255)


def _usage_color(percent: float) -> QColor:
    if percent >= 85:
        return RED
    if percent >= 60:
        return YELLOW
    return GREEN


def _battery_color(percent: float, low: int, critical: int) -> QColor:
    if percent <= critical:
        return RED
    if percent <= low:
        return YELLOW
    return GREEN


# ---- tiny custom progress bar ---------------------------------------------
class Bar(QWidget):
    """A thin, rounded progress bar with full control over colours."""

    def __init__(self, height: int = 6, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._color = GREEN
        self.setFixedHeight(height)
        self.setMinimumWidth(60)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set(self, percent: float, color: QColor) -> None:
        self._value = max(0.0, min(100.0, percent))
        self._color = color
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect().adjusted(0, 0, 0, 0))
        radius = r.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(TRACK)
        p.drawRoundedRect(r, radius, radius)
        if self._value > 0:
            width = max(r.height(), r.width() * self._value / 100.0)
            fill = QRectF(r.x(), r.y(), width, r.height())
            p.setBrush(self._color)
            p.drawRoundedRect(fill, radius, radius)


# ---- one metric row --------------------------------------------------------
class MetricCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.icon = QLabel()
        self.icon.setFixedWidth(22)
        self.icon.setStyleSheet("font-size: 15px; background: transparent;")

        self.name = QLabel()
        self.name.setStyleSheet("color: #ebecf0; font-size: 11px; font-weight: 600; background: transparent;")

        self.detail = QLabel()
        self.detail.setStyleSheet("color: #9698a0; font-size: 9px; background: transparent;")

        self.value = QLabel()
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value.setStyleSheet("color: #ebecf0; font-size: 12px; font-weight: 700; background: transparent;")

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        top.addWidget(self.icon)
        top.addWidget(self.name)
        top.addWidget(self.detail)
        top.addStretch(1)
        top.addWidget(self.value)

        self.bar = Bar(height=5)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addLayout(top)
        layout.addWidget(self.bar)
        self.setLayout(layout)

    def update_card(
        self,
        icon: str,
        name: str,
        value_text: str,
        percent: float | None,
        color: QColor,
        detail: str = "",
    ) -> None:
        self.icon.setText(icon)
        self.name.setText(name)
        self.detail.setText(detail)
        self.value.setText(value_text)
        if percent is None:
            self.bar.setVisible(False)
        else:
            self.bar.setVisible(True)
            self.bar.set(percent, color)


# ---- remote device row -----------------------------------------------------
class RemoteDeviceCard(QWidget):
    """Compact card for a connected remote device (battery-forward)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.icon = QLabel("📱")
        self.icon.setFixedWidth(22)
        self.icon.setStyleSheet("font-size: 15px; background: transparent;")

        self.name = QLabel()
        self.name.setStyleSheet("color: #ebecf0; font-size: 11px; font-weight: 600; background: transparent;")

        self.value = QLabel()
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value.setStyleSheet("color: #ebecf0; font-size: 12px; font-weight: 700; background: transparent;")

        self.detail = QLabel()
        self.detail.setStyleSheet("color: #9698a0; font-size: 9px; background: transparent;")

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        top.addWidget(self.icon)
        top.addWidget(self.name)
        top.addStretch(1)
        top.addWidget(self.value)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(top)
        layout.addWidget(self.detail)
        self.setLayout(layout)

    def update_card(self, device_name: str, data: dict) -> None:
        self.name.setText(device_name)
        battery = data.get("battery") or {}
        cpu = data.get("cpu") or {}
        mem = data.get("memory") or {}

        if battery.get("present"):
            pct = battery.get("percent") or 0.0
            if battery.get("plugged"):
                self.icon.setText("⚡")
            else:
                self.icon.setText("🔋")
            self.value.setText(f"{pct:.0f}%")
            color = _battery_color(pct, 30, 15)
            self.value.setStyleSheet(
                f"color: {color.name()}; font-size: 12px; font-weight: 700; background: transparent;"
            )
        else:
            self.icon.setText("🔌")
            self.value.setText("AC")
            self.value.setStyleSheet("color: #6096ff; font-size: 12px; font-weight: 700; background: transparent;")

        bits = []
        status = battery.get("status")
        if status and status != "no_battery":
            bits.append({"charging": "充电中", "full": "已充满", "discharging": "放电中"}.get(status, status))
        if cpu.get("percent") is not None:
            bits.append(f"CPU {cpu['percent']:.0f}%")
        if mem.get("percent") is not None:
            bits.append(f"内存 {mem['percent']:.0f}%")
        self.detail.setText(" · ".join(bits))


# ---- background collector thread ------------------------------------------
class MetricsWorker(QThread):
    """Collects metrics on a background thread.

    The interval can be changed at runtime via :meth:`set_interval` without
    recreating the thread (recreating risks deleting a still-running QThread,
    which crashes the app). Sleep is done in small increments so ``stop()`` and
    interval changes take effect promptly.
    """

    metrics_ready = Signal(object)

    def __init__(self, interval_seconds: float, parent=None):
        super().__init__(parent)
        self._interval_ms = max(200, int(interval_seconds * 1000))
        self._running = True
        self._collector = MetricsCollector()

    def set_interval(self, interval_seconds: float) -> None:
        self._interval_ms = max(200, int(interval_seconds * 1000))

    def run(self) -> None:  # noqa: D102
        self._collector.collect()  # prime cpu_percent
        while self._running:
            try:
                payload = self._collector.collect()
                self.metrics_ready.emit(payload)
            except Exception:
                pass
            # Sleep in small slices so stop()/set_interval() react quickly.
            slept = 0
            while self._running and slept < self._interval_ms:
                self.msleep(100)
                slept += 100

    def stop(self) -> None:
        self._running = False


# ---- the widget itself -----------------------------------------------------
class StatusWidget(QWidget):
    request_settings = Signal()
    request_hide = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._drag_offset: QPoint | None = None
        self._remote_cards: dict[str, RemoteDeviceCard] = {}

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnBottomHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFixedWidth(280)
        self.setMouseTracking(True)

        self._build_ui()

        # Worker thread for metric collection.
        self._worker = MetricsWorker(config.update_interval_seconds)
        self._worker.metrics_ready.connect(self._on_metrics)
        self._worker.start()

    # -- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(7)

        # Header
        title = QLabel("Status Tools")
        title.setStyleSheet("color: #ebecf0; font-size: 13px; font-weight: 700; background: transparent;")

        btn_settings = self._icon_button("⚙", "设置")
        btn_settings.clicked.connect(self.request_settings.emit)
        btn_hide = self._icon_button("✕", "隐藏到托盘")
        btn_hide.clicked.connect(self.request_hide.emit)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(btn_settings)
        header.addWidget(btn_hide)

        # Cards
        self.card_cpu = MetricCard()
        self.card_gpu = MetricCard()
        self.card_mem = MetricCard()
        self.card_disk = MetricCard()
        self.card_battery = MetricCard()

        root.addLayout(header)
        for card in (self.card_cpu, self.card_gpu, self.card_mem, self.card_disk, self.card_battery):
            root.addWidget(card)

        # Remote (connected) devices section
        self.remote_header = QLabel("已连接设备")
        self.remote_header.setStyleSheet(
            "color: #9698a0; font-size: 10px; font-weight: 600; background: transparent;"
        )
        self.remote_header.setVisible(False)
        self.remote_layout = QVBoxLayout()
        self.remote_layout.setContentsMargins(0, 0, 0, 0)
        self.remote_layout.setSpacing(8)

        root.addSpacing(2)
        root.addWidget(self.remote_header)
        root.addLayout(self.remote_layout)
        root.addStretch(1)

        self.setLayout(root)

    @staticmethod
    def _icon_button(glyph: str, tooltip: str) -> QPushButton:
        b = QPushButton(glyph)
        b.setFixedSize(24, 24)
        b.setToolTip(tooltip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.06); color: #c8cad2;"
            " border: none; border-radius: 6px; font-size: 13px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.14); color: #ffffff; }"
        )
        return b

    # -- data binding -------------------------------------------------------
    def _on_metrics(self, payload: MetricsPayload) -> None:
        m = payload

        cpu_bits = [f"{m.cpu.core_count} 核"]
        if m.cpu.temperature_c is not None:
            cpu_bits.append(f"{m.cpu.temperature_c:.0f}°C")
        self.card_cpu.update_card(
            "🧮", "CPU", f"{m.cpu.percent:.0f}%", m.cpu.percent, _usage_color(m.cpu.percent),
            detail=" · ".join(cpu_bits),
        )

        if m.gpu.available:
            vram = f"{m.gpu.memory_used_mb/1024:.1f}/{m.gpu.memory_total_mb/1024:.1f} GB"
            temp = f"{m.gpu.temperature_c:.0f}°C" if m.gpu.temperature_c is not None else ""
            detail = " · ".join(x for x in (vram, temp) if x)
            self.card_gpu.update_card(
                "🎮", "GPU", f"{m.gpu.percent:.0f}%", m.gpu.percent, _usage_color(m.gpu.percent), detail=detail,
            )
        else:
            self.card_gpu.update_card("🎮", "GPU", "N/A", None, FG_DIM, detail="不可用")

        self.card_mem.update_card(
            "🧠", "内存", f"{m.memory.percent:.0f}%", m.memory.percent, _usage_color(m.memory.percent),
            detail=f"{m.memory.used_mb/1024:.1f}/{m.memory.total_mb/1024:.1f} GB",
        )

        self.card_disk.update_card(
            "💽", "磁盘", f"{m.disk.percent:.0f}%", m.disk.percent, _usage_color(m.disk.percent),
            detail=f"{m.disk.used_gb:.0f}/{m.disk.total_gb:.0f} GB",
        )

        b = m.battery
        th = self.config.thresholds
        if not b.present:
            # No battery (desktop) -> plug icon, no percentage bar.
            self.card_battery.update_card("🔌", "电源", "AC 供电", None, ACCENT, detail="未检测到电池")
        else:
            pct = b.percent if b.percent is not None else 0.0
            if b.plugged:
                icon = "⚡"
                state = "已充满" if b.status == "full" else "充电中"
            else:
                icon = "🔋"
                state = "放电中"
            self.card_battery.update_card(
                icon, "电量", f"{pct:.0f}%", pct, _battery_color(pct, th.battery_low_percent, th.battery_critical_percent),
                detail=state,
            )

    # -- painting -----------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)

        # Glass body: vertical gradient, slightly lighter at the top.
        opacity = self.config.widget_opacity
        top = QColor(BG)
        top.setAlphaF(max(0.0, min(1.0, opacity - 0.10)))
        bottom = QColor(BG)
        bottom.setAlphaF(max(0.0, min(1.0, opacity + 0.02)))
        grad = QLinearGradient(0.0, 0.0, 0.0, rect.height())
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bottom)
        p.fillPath(path, QBrush(grad))

        # Top highlight + outer border for a "glass" edge.
        p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.drawPath(path)

    # -- dragging -----------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None:
            self.config.widget_x = self.x()
            self.config.widget_y = self.y()
            self.config.save()
        self._drag_offset = None
        event.accept()

    # -- lifecycle ----------------------------------------------------------
    def restore_position(self, fallback: QPoint) -> None:
        if self.config.widget_x is not None and self.config.widget_y is not None:
            self.move(self.config.widget_x, self.config.widget_y)
        else:
            self.move(fallback)

    def set_interval(self, seconds: float) -> None:
        """Update the collector's refresh interval without restarting the thread."""
        self._worker.set_interval(seconds)

    # -- remote devices -----------------------------------------------------
    def update_remote_device(self, device_id: str, name: str, data: dict) -> None:
        card = self._remote_cards.get(device_id)
        if card is None:
            card = RemoteDeviceCard()
            self._remote_cards[device_id] = card
            self.remote_layout.addWidget(card)
        card.update_card(name, data)
        self.remote_header.setVisible(True)
        # Grow the window so the new card is actually visible.
        self.adjustSize()
        self.update()

    def remove_remote_device(self, device_id: str) -> None:
        card = self._remote_cards.pop(device_id, None)
        if card is not None:
            self.remote_layout.removeWidget(card)
            card.deleteLater()
        if not self._remote_cards:
            self.remote_header.setVisible(False)
        self.adjustSize()
        self.update()

    def close_to_tray(self) -> None:
        self.hide()

    def shutdown(self) -> None:
        try:
            self._worker.metrics_ready.disconnect(self._on_metrics)
        except Exception:
            pass
        self._worker.stop()
        self._worker.wait(1500)
