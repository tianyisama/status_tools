"""status_tools desktop entry point.

Run with:  python main.py
"""

from __future__ import annotations

import os
import platform
import sys

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QApplication

from statustools.alerts.engine import AlertEngine
from statustools.alerts.notifier import Notifier
from statustools.config import Config
from statustools.net.discovery import DiscoveryResponder
from statustools.net.server import MetricsServer, NetBridge
from statustools.ui.embedding import apply_embedding
from statustools.ui.settings import SettingsDialog
from statustools.ui.tray import TrayController
from statustools.ui.widget import StatusWidget


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Status Tools")
    app.setQuitOnLastWindowClosed(False)  # closing the widget hides to tray

    config = Config.load()

    widget = StatusWidget(config)
    tray = TrayController()
    # Built lazily on first open: constructing it probes the network for local IPs,
    # which can take seconds and would delay startup.
    settings = None

    # --- networking + alerts ------------------------------------------------
    device_name = platform.node() or "Desktop"
    device_id = f"desktop-{device_name}".lower()
    notifier = Notifier(tray)
    engine = AlertEngine(config, notifier)
    bridge = NetBridge()
    server = MetricsServer(config, bridge, device_id, device_name)
    discovery = DiscoveryResponder(config, device_id, device_name)

    def on_device_connected(did: str, name: str) -> None:
        engine.on_device_connected(did, name)

    def on_device_metrics(did: str, data) -> None:
        engine.on_metrics(did, data)
        widget.update_remote_device(did, engine.device_name(did), data)

    def on_device_disconnected(did: str) -> None:
        engine.on_device_disconnected(did)
        widget.remove_remote_device(did)

    bridge.device_connected.connect(on_device_connected)
    bridge.device_metrics.connect(on_device_metrics)
    bridge.device_disconnected.connect(on_device_disconnected)

    server.start()
    discovery.start()

    # --- wire up signals ----------------------------------------------------
    def show_widget() -> None:
        widget.show()

    def hide_widget() -> None:
        widget.hide()

    def toggle_widget() -> None:
        hide_widget() if widget.isVisible() else show_widget()

    def open_settings() -> None:
        nonlocal settings
        if settings is None:
            settings = SettingsDialog(config)
            settings.saved.connect(apply_live_settings)
        settings.exec()

    def apply_live_settings() -> None:
        # Opacity + interval apply immediately; embed mode applies on next launch.
        widget.update()
        widget.set_interval(config.update_interval_seconds)
        # Push updated thresholds to connected clients.
        server.broadcast_config(
            {
                "battery_low_percent": config.thresholds.battery_low_percent,
                "battery_critical_percent": config.thresholds.battery_critical_percent,
                "cpu_high_percent": config.thresholds.cpu_high_percent,
                "memory_high_percent": config.thresholds.memory_high_percent,
                "disk_high_percent": config.thresholds.disk_high_percent,
            },
            config.charging_stall_minutes,
        )

    widget.request_settings.connect(open_settings)
    widget.request_hide.connect(hide_widget)

    tray.show_widget.connect(show_widget)
    tray.hide_widget.connect(hide_widget)
    tray.toggle_widget.connect(toggle_widget)
    tray.open_settings.connect(open_settings)
    tray.quit_app.connect(app.quit)

    # --- position + show ----------------------------------------------------
    screen = app.primaryScreen().availableGeometry()
    fallback = QPoint(screen.right() - widget.width() - 40, screen.top() + 60)

    # Show the UI immediately; the desktop-embedding step below can block briefly.
    widget.show()
    tray.show()

    # Windows frosted-glass (acrylic) backdrop, best-effort.
    if config.acrylic and os.name == "nt":
        try:
            from statustools.ui.embedding.windows import set_acrylic

            set_acrylic(int(widget.winId()))
        except Exception:
            pass

    # Try to embed into the desktop layer; otherwise keep the bottom-most window.
    apply_embedding(widget, config)
    widget.restore_position(fallback)

    # --- teardown -----------------------------------------------------------
    def shutdown() -> None:
        server.stop()
        discovery.stop()
        widget.shutdown()
        config.save()

    app.aboutToQuit.connect(shutdown)

    # Optional headless/test hook: ST_AUTO_QUIT_MS=<ms> quits after a delay.
    auto_quit = os.environ.get("ST_AUTO_QUIT_MS")
    if auto_quit:
        QTimer.singleShot(int(auto_quit), app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
