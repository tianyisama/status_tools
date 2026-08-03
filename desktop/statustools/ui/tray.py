"""System-tray icon and toast notifications.

Uses Qt's built-in ``QSystemTrayIcon`` so there is no extra dependency. On
Windows 10/11 ``showMessage`` surfaces as a system toast / Action-Center entry.
The icon is drawn programmatically, so no asset file is required for the MVP.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def make_icon(size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(96, 150, 255))
    p.drawRoundedRect(QRectF(2, 2, size - 4, size - 4), size * 0.22, size * 0.22)
    p.setPen(QColor(255, 255, 255))
    p.setFont(QFont("Segoe UI", int(size * 0.42), QFont.Weight.Bold))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "S")
    p.end()
    return QIcon(pm)


class TrayController(QObject):
    show_widget = Signal()
    hide_widget = Signal()
    toggle_widget = Signal()
    open_settings = Signal()
    quit_app = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon = QSystemTrayIcon(make_icon())
        self._icon.setToolTip("Status Tools")

        menu = QMenu()
        act_show = menu.addAction("显示小组件")
        act_hide = menu.addAction("隐藏小组件")
        act_settings = menu.addAction("设置…")
        menu.addSeparator()
        act_quit = menu.addAction("退出")

        act_show.triggered.connect(self.show_widget.emit)
        act_hide.triggered.connect(self.hide_widget.emit)
        act_settings.triggered.connect(self.open_settings.emit)
        act_quit.triggered.connect(self.quit_app.emit)

        self._icon.setContextMenu(menu)
        self._icon.activated.connect(self._on_activated)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # left click
            self.toggle_widget.emit()

    def show(self) -> None:
        self._icon.show()

    def notify(self, title: str, message: str, warning: bool = True) -> None:
        icon = (
            QSystemTrayIcon.MessageIcon.Warning
            if warning
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._icon.showMessage(title, message, icon, 8000)
