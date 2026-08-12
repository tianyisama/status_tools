"""The frameless, translucent, draggable desktop widget.

It is *not* always-on-top: it uses ``WindowStaysOnBottomHint`` in fallback mode
and (optionally) gets re-parented into the desktop layer via WorkerW. Metric
collection happens on a worker ``QThread`` so the UI never blocks on the
``nvidia-smi`` subprocess.

The widget is a rounded glass card whose text colours adapt to the desktop
background: when ``config.theme_mode == "auto"``, a timer samples the screen
luminance around the widget and swaps between the dark and light glass
palettes from :mod:`.theme`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QRectF, Signal, QThread, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..metrics.collector import MetricsCollector
from ..metrics.models import MetricsPayload
from .theme import WidgetTheme, get, hex, rgba, resolve, sample_wallpaper_luminance

_CORNER = 18  # widget outer corner radius
_FALLBACK_THEME = get("dark")  # used before the first apply_theme() call


def _usage_color(percent: float, theme: WidgetTheme) -> QColor:
    if percent >= 85:
        return theme.bad
    if percent >= 60:
        return theme.warn
    return theme.good


def _battery_color(percent: float, low: int, critical: int, theme: WidgetTheme) -> QColor:
    if percent <= critical:
        return theme.bad
    if percent <= low:
        return theme.warn
    return theme.good


# ---- tiny custom progress bar ---------------------------------------------
class Bar(QWidget):
    """A thin, rounded progress bar with full control over colours."""

    def __init__(self, height: int = 6, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._color = QColor(76, 217, 123)
        self._track = QColor(255, 255, 255, 22)
        self.setFixedHeight(height)
        self.setMinimumWidth(60)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set(self, percent: float, color: QColor) -> None:
        self._value = max(0.0, min(100.0, percent))
        self._color = color
        self.update()

    def apply_theme(self, theme: WidgetTheme) -> None:
        self._track = theme.track
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        radius = r.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._track)
        p.drawRoundedRect(r, radius, radius)
        if self._value > 0:
            width = max(r.height(), r.width() * self._value / 100.0)
            fill = QRectF(r.x(), r.y(), width, r.height())
            p.setBrush(self._color)
            p.drawRoundedRect(fill, radius, radius)


# ---- one compact metric line ----------------------------------------------
class MetricRow(QWidget):
    """A single dense line: icon | name | bar | value | detail.

    Deliberately borderless so the widget stays compact and the clear glass
    shows through; the bar carries the usage colour, the value stays neutral.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._theme = None  # type: WidgetTheme | None

        self.icon = QLabel()
        self.icon.setFixedWidth(18)
        self.icon.setStyleSheet("font-size: 14px; background: transparent;")

        self.name = QLabel()
        self.name.setFixedWidth(44)

        self.bar = Bar(height=4)

        self.value = QLabel()
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.detail = QLabel()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.icon)
        layout.addWidget(self.name)
        layout.addWidget(self.bar, stretch=1)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)
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

    def apply_theme(self, theme: WidgetTheme) -> None:
        self._theme = theme
        self.name.setStyleSheet(
            f"color: {hex(theme.fg)}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        self.detail.setStyleSheet(
            f"color: {hex(theme.fg_dim)}; font-size: 9px; background: transparent;"
        )
        self.value.setStyleSheet(
            f"color: {hex(theme.fg)}; font-size: 12px; font-weight: 700; background: transparent;"
        )
        self.bar.apply_theme(theme)


# ---- remote device card ----------------------------------------------------
class RemoteDeviceCard(QWidget):
    """A small rounded card for a connected remote device (battery-forward)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._theme = None  # type: WidgetTheme | None
        self._accent = QColor(96, 150, 255)

        self.icon = QLabel("📱")
        self.icon.setFixedWidth(20)
        self.icon.setStyleSheet("font-size: 14px; background: transparent;")

        self.name = QLabel()
        self.value = QLabel()
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.bar = Bar(height=4)
        self.detail = QLabel()

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        top.addWidget(self.icon)
        top.addWidget(self.name)
        top.addStretch(1)
        top.addWidget(self.value)

        layout = QVBoxLayout()
        layout.setContentsMargins(7, 5, 7, 5)
        layout.setSpacing(3)
        layout.addLayout(top)
        layout.addWidget(self.bar)
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
            color = _battery_color(pct, 30, 15, self._theme or _FALLBACK_THEME)
            self.value.setStyleSheet(
                f"color: {hex(color)}; font-size: 12px; font-weight: 700; background: transparent;"
            )
            self.bar.setVisible(True)
            self.bar.set(pct, color)
        else:
            self.icon.setText("🔌")
            self.value.setText("AC")
            self.value.setStyleSheet(
                f"color: {hex(self._accent)}; font-size: 12px; font-weight: 700; background: transparent;"
            )
            self.bar.setVisible(False)

        bits = []
        status = battery.get("status")
        if status and status != "no_battery":
            bits.append({"charging": "充电中", "full": "已充满", "discharging": "放电中"}.get(status, status))
        if cpu.get("percent") is not None:
            cpu_temp = cpu.get("temperature_c")
            temp_txt = f" {cpu_temp:.0f}°C" if cpu_temp is not None else ""
            bits.append(f"CPU {cpu['percent']:.0f}%{temp_txt}")
        if mem.get("percent") is not None:
            bits.append(f"内存 {mem['percent']:.0f}%")
        self.detail.setText(" · ".join(bits))

    def apply_theme(self, theme: WidgetTheme) -> None:
        self._theme = theme
        self._accent = theme.accent
        self.setStyleSheet(
            "RemoteDeviceCard { background: %s; border: 1px solid %s; border-radius: 11px; }"
            % (rgba(theme.card), rgba(theme.card_border))
        )
        self.name.setStyleSheet(
            f"color: {hex(theme.fg)}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        self.detail.setStyleSheet(
            f"color: {hex(theme.fg_dim)}; font-size: 9px; background: transparent;"
        )
        self.bar.apply_theme(theme)


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
    # Emits the local MetricsPayload (protocol dict) on every refresh so the
    # server can forward this device's own metrics to connected peers.
    local_metrics = Signal(object)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._drag_offset: QPoint | None = None
        self._remote_cards: dict[str, RemoteDeviceCard] = {}
        self._theme = get(config.theme_mode if config.theme_mode != "auto" else "dark")
        self._theme_timer = QTimer(self)
        self._theme_timer.setInterval(4000)
        self._theme_timer.timeout.connect(self._adapt_theme)

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
        self._apply_theme(self._theme)
        self._theme_timer.start()

        # Worker thread for metric collection.
        self._worker = MetricsWorker(config.update_interval_seconds)
        self._worker.metrics_ready.connect(self._on_metrics)
        self._worker.start()

    # -- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(3)

        # Header
        title = QLabel("Status Tools")
        self.title = title
        title.setStyleSheet("font-size: 12px; font-weight: 700; background: transparent;")

        self._buttons: list[QPushButton] = []
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

        # Compact metric lines
        self.card_cpu = MetricRow()
        self.card_gpu = MetricRow()
        self.card_mem = MetricRow()
        self.card_disk = MetricRow()
        self.card_battery = MetricRow()
        self._cards = (
            self.card_cpu,
            self.card_gpu,
            self.card_mem,
            self.card_disk,
            self.card_battery,
        )

        root.addLayout(header)
        root.addSpacing(1)
        for card in self._cards:
            root.addWidget(card)

        # Remote (connected) devices section
        self.remote_header = QLabel("已连接设备")
        self.remote_header.setStyleSheet("font-size: 10px; font-weight: 600; background: transparent;")
        self.remote_header.setVisible(False)
        self.remote_layout = QVBoxLayout()
        self.remote_layout.setContentsMargins(0, 0, 0, 0)
        self.remote_layout.setSpacing(6)

        root.addSpacing(2)
        root.addWidget(self.remote_header)
        root.addLayout(self.remote_layout)
        root.addStretch(1)

        self.setLayout(root)

    def _icon_button(self, glyph: str, tooltip: str) -> QPushButton:
        b = QPushButton(glyph)
        b.setFixedSize(22, 22)
        b.setToolTip(tooltip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        self._buttons.append(b)
        return b

    # -- theming ------------------------------------------------------------
    def refresh_theme(self) -> None:
        """Sample the wallpaper and apply the theme immediately (e.g. at startup)."""
        self._adapt_theme(force=True)

    def set_theme_mode(self, mode: str) -> None:
        """Apply a new theme_mode ("auto"/"dark"/"light") right away."""
        self.config.theme_mode = mode
        self._adapt_theme(force=True)

    def _adapt_theme(self, force: bool = False) -> None:
        if self.config.theme_mode != "auto":
            new_name = self.config.theme_mode
        else:
            lum = sample_wallpaper_luminance(self)
            if lum is None:
                return  # keep current theme
            new_name = resolve("auto", lum, self._theme.name)
        if force or new_name != self._theme.name:
            self._apply_theme(get(new_name))

    def _apply_theme(self, theme: WidgetTheme) -> None:
        self._theme = theme
        self.title.setStyleSheet(
            f"color: {hex(theme.fg)}; font-size: 13px; font-weight: 700; background: transparent;"
        )
        self.remote_header.setStyleSheet(
            f"color: {hex(theme.fg_dim)}; font-size: 10px; font-weight: 600; background: transparent;"
        )
        for b in self._buttons:
            b.setStyleSheet(
                "QPushButton { background: %s; color: %s; border: none; border-radius: 7px; font-size: 13px; }"
                "QPushButton:hover { background: %s; color: %s; }"
                % (rgba(theme.button), hex(theme.button_fg), rgba(theme.button_hover), hex(theme.fg))
            )
        for card in self._cards:
            card.apply_theme(theme)
        for card in self._remote_cards.values():
            card.apply_theme(theme)
        self.update()

    # -- data binding -------------------------------------------------------
    def _on_metrics(self, payload: MetricsPayload) -> None:
        m = payload
        t = self._theme

        cpu_bits = [f"{m.cpu.core_count} 核"]
        if m.cpu.temperature_c is not None:
            cpu_bits.append(f"{m.cpu.temperature_c:.0f}°C")
        self.card_cpu.update_card(
            "🧮", "CPU", f"{m.cpu.percent:.0f}%", m.cpu.percent, _usage_color(m.cpu.percent, t),
            detail=" · ".join(cpu_bits),
        )

        if m.gpu.available:
            vram = f"{m.gpu.memory_used_mb/1024:.1f}/{m.gpu.memory_total_mb/1024:.1f} GB"
            temp = f"{m.gpu.temperature_c:.0f}°C" if m.gpu.temperature_c is not None else ""
            detail = " · ".join(x for x in (vram, temp) if x)
            self.card_gpu.update_card(
                "🎮", "GPU", f"{m.gpu.percent:.0f}%", m.gpu.percent, _usage_color(m.gpu.percent, t), detail=detail,
            )
        else:
            self.card_gpu.update_card("🎮", "GPU", "N/A", None, t.fg_dim, detail="不可用")

        self.card_mem.update_card(
            "🧠", "内存", f"{m.memory.percent:.0f}%", m.memory.percent, _usage_color(m.memory.percent, t),
            detail=f"{m.memory.used_mb/1024:.1f}/{m.memory.total_mb/1024:.1f} GB",
        )

        self.card_disk.update_card(
            "💽", "磁盘", f"{m.disk.percent:.0f}%", m.disk.percent, _usage_color(m.disk.percent, t),
            detail=f"{m.disk.used_gb:.0f}/{m.disk.total_gb:.0f} GB",
        )

        b = m.battery
        th = self.config.thresholds
        if not b.present:
            # No battery (desktop) -> plug icon, no percentage bar.
            self.card_battery.update_card("🔌", "电源", "AC 供电", None, t.accent, detail="未检测到电池")
        else:
            pct = b.percent if b.percent is not None else 0.0
            if b.plugged:
                icon = "⚡"
                state = "已充满" if b.status == "full" else "充电中"
            else:
                icon = "🔋"
                state = "放电中"
            self.card_battery.update_card(
                icon, "电量", f"{pct:.0f}%", pct,
                _battery_color(pct, th.battery_low_percent, th.battery_critical_percent, t),
                detail=state,
            )

        # Forward our own metrics to peers via the server (peer-to-peer display).
        try:
            self.local_metrics.emit(m.to_protocol_dict())
        except Exception:
            pass

    # -- painting -----------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, _CORNER, _CORNER)

        # Glass body: near-uniform tint, very slightly lighter at the top.
        # The opacity setting scales the body alpha; at the default ~0.42 the
        # wallpaper shows through crisply (clear glass, not frosted).
        opacity = self.config.widget_opacity
        top = QColor(self._theme.bg)
        top.setAlphaF(max(0.0, min(1.0, opacity - 0.04)))
        bottom = QColor(self._theme.bg_dim)
        bottom.setAlphaF(max(0.0, min(1.0, opacity + 0.01)))
        grad = QLinearGradient(0.0, 0.0, 0.0, rect.height())
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bottom)
        p.fillPath(path, QBrush(grad))

        # Soft top glow for glass depth (clipped to the card).
        p.save()
        p.setClipPath(path)
        glow = QLinearGradient(0.0, 0.0, 0.0, rect.height() * 0.45)
        glow.setColorAt(0.0, self._theme.glow)
        glow.setColorAt(1.0, QColor(self._theme.glow.red(), self._theme.glow.green(),
                                    self._theme.glow.blue(), 0))
        p.fillRect(rect, QBrush(glow))
        p.restore()

        # Outer edge.
        p.setPen(QPen(self._theme.border, 1))
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
            card.apply_theme(self._theme)
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
        self._theme_timer.stop()
        try:
            self._worker.metrics_ready.disconnect(self._on_metrics)
        except Exception:
            pass
        self._worker.stop()
        self._worker.wait(1500)
