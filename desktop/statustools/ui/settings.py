"""Settings dialog (standard Qt widgets, dark-styled).

Writes back into the shared :class:`Config` and emits ``saved`` so the caller
can re-apply live settings (opacity, embed mode, refresh interval, ports).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..net.server import local_ip_addresses

_DARK = """
QDialog, QWidget { background: #1c1c24; color: #ebecf0; font-size: 12px; }
QGroupBox { border: 1px solid #34343f; border-radius: 8px; margin-top: 12px;
            padding: 10px 8px 8px 8px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #9698a0; }
QSpinBox, QDoubleSpinBox { background: #26262f; border: 1px solid #34343f;
            border-radius: 5px; padding: 3px 6px; }
QComboBox { background: #26262f; border: 1px solid #34343f;
            border-radius: 5px; padding: 3px 8px; }
QComboBox QAbstractItemView { background: #26262f; color: #ebecf0;
            border: 1px solid #34343f; selection-background-color: #6096ff;
            selection-color: #ffffff; }
QComboBox::drop-down { border: none; width: 18px; }
QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px;
            border: 1px solid #45454f; background: #26262f; }
QCheckBox::indicator:checked { background: #6096ff; border-color: #6096ff; }
QDialogButtonBox QPushButton { background: #26262f; border: 1px solid #34343f;
            border-radius: 6px; padding: 6px 14px; }
QDialogButtonBox QPushButton:hover { background: #30303c; }
QScrollArea { border: none; }
"""


class SettingsDialog(QDialog):
    saved = Signal()

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Status Tools · 设置")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(_DARK)
        self._build()

    # -- construction -------------------------------------------------------
    def _build(self) -> None:
        c = self.config

        # Appearance
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.5, 60.0)
        self.spin_interval.setSingleStep(0.5)
        self.spin_interval.setSuffix(" 秒")
        self.spin_interval.setValue(c.update_interval_seconds)

        self.spin_opacity = QDoubleSpinBox()
        self.spin_opacity.setRange(0.3, 1.0)
        self.spin_opacity.setSingleStep(0.05)
        self.spin_opacity.setValue(c.widget_opacity)

        self.chk_embed = QCheckBox("嵌入桌面（Windows WorkerW；关闭则用置底窗口）")
        self.chk_embed.setChecked(c.embed_desktop)

        self.chk_acrylic = QCheckBox("玻璃 / 亚克力毛玻璃背景（Windows，需重启或保存后生效）")
        self.chk_acrylic.setChecked(c.acrylic)

        self.combo_theme = QComboBox()
        self.combo_theme.addItem("自动（跟随壁纸明暗）", "auto")
        self.combo_theme.addItem("深色", "dark")
        self.combo_theme.addItem("浅色", "light")
        idx = self.combo_theme.findData(c.theme_mode)
        self.combo_theme.setCurrentIndex(max(0, idx))

        g_appear = QGroupBox("外观")
        f_appear = QFormLayout()
        f_appear.addRow("刷新间隔", self.spin_interval)
        f_appear.addRow("不透明度", self.spin_opacity)
        f_appear.addRow("外观模式", self.combo_theme)
        f_appear.addRow(self.chk_embed)
        f_appear.addRow(self.chk_acrylic)
        g_appear.setLayout(f_appear)

        # Network
        self.chk_server = QCheckBox("启用服务端（接收手机上报）")
        self.chk_server.setChecked(c.server_enabled)

        self.spin_service_port = QSpinBox()
        self.spin_service_port.setRange(1024, 65535)
        self.spin_service_port.setValue(c.service_port)

        self.spin_discovery_port = QSpinBox()
        self.spin_discovery_port.setRange(1024, 65535)
        self.spin_discovery_port.setValue(c.discovery_port)

        g_net = QGroupBox("网络")
        f_net = QFormLayout()
        f_net.addRow(self.chk_server)
        f_net.addRow("服务端口 (WebSocket)", self.spin_service_port)
        f_net.addRow("发现端口 (UDP)", self.spin_discovery_port)

        ips = local_ip_addresses()
        ip_text = "、".join(ips) if ips else "未检测到（请检查网络）"
        ip_label = QLabel(f"本机 IP（填到手机端）：{ip_text} : {c.service_port}")
        ip_label.setWordWrap(True)
        ip_label.setStyleSheet("color: #6096ff; font-size: 11px;")
        f_net.addRow(ip_label)
        g_net.setLayout(f_net)

        # Alert thresholds
        th = c.thresholds
        self.spin_batt_low = self._pct(th.battery_low_percent)
        self.spin_batt_crit = self._pct(th.battery_critical_percent)
        self.spin_cpu_high = self._pct(th.cpu_high_percent)
        self.spin_mem_high = self._pct(th.memory_high_percent)
        self.spin_disk_high = self._pct(th.disk_high_percent)

        g_alert = QGroupBox("告警阈值")
        f_alert = QFormLayout()
        f_alert.addRow("电量低 (%)", self.spin_batt_low)
        f_alert.addRow("电量危急 (%)", self.spin_batt_crit)
        f_alert.addRow("CPU 过高 (%)", self.spin_cpu_high)
        f_alert.addRow("内存过高 (%)", self.spin_mem_high)
        f_alert.addRow("磁盘过高 (%)", self.spin_disk_high)
        g_alert.setLayout(f_alert)

        # Charging stall
        self.spin_stall = QSpinBox()
        self.spin_stall.setRange(1, 240)
        self.spin_stall.setSuffix(" 分钟")
        self.spin_stall.setValue(c.charging_stall_minutes)

        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(10, 86400)
        self.spin_cooldown.setSuffix(" 秒")
        self.spin_cooldown.setValue(c.notification_cooldown_seconds)

        g_stall = QGroupBox("充电失速 / 防打扰")
        f_stall = QFormLayout()
        f_stall.addRow("插电未增长阈值", self.spin_stall)
        f_stall.addRow("通知冷却", self.spin_cooldown)
        g_stall.setLayout(f_stall)

        # Assemble in a scroll area
        content = QWidget()
        v = QVBoxLayout()
        v.addWidget(g_appear)
        v.addWidget(g_net)
        v.addWidget(g_alert)
        v.addWidget(g_stall)
        content.setLayout(v)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        outer = QVBoxLayout()
        outer.addWidget(scroll)
        outer.addWidget(buttons)
        self.setLayout(outer)

    @staticmethod
    def _pct(value: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(0, 100)
        s.setSuffix(" %")
        s.setValue(value)
        return s

    # -- actions ------------------------------------------------------------
    def _save(self) -> None:
        c = self.config
        c.update_interval_seconds = self.spin_interval.value()
        c.widget_opacity = self.spin_opacity.value()
        c.theme_mode = self.combo_theme.currentData()
        c.embed_desktop = self.chk_embed.isChecked()
        c.acrylic = self.chk_acrylic.isChecked()

        c.server_enabled = self.chk_server.isChecked()
        c.service_port = self.spin_service_port.value()
        c.discovery_port = self.spin_discovery_port.value()

        c.thresholds.battery_low_percent = self.spin_batt_low.value()
        c.thresholds.battery_critical_percent = self.spin_batt_crit.value()
        c.thresholds.cpu_high_percent = self.spin_cpu_high.value()
        c.thresholds.memory_high_percent = self.spin_mem_high.value()
        c.thresholds.disk_high_percent = self.spin_disk_high.value()

        c.charging_stall_minutes = self.spin_stall.value()
        c.notification_cooldown_seconds = self.spin_cooldown.value()

        c.save()
        self.saved.emit()
        self.accept()
