# status_tools

跨平台资源监控应用：**Windows / Android / Linux**。实时展示 CPU、GPU、内存、磁盘、电量（无电池的设备显示插电图标）。桌面端以**嵌入桌面的小组件**呈现（会被普通窗口遮挡，不是始终置顶）；安卓端为普通 App，并可把自身指标推送给桌面端汇总与告警。

## 架构一览

| 端 | 技术 | 构建 |
|---|---|---|
| Windows + Linux 桌面 | Python + PySide6 | Windows 本机 PyInstaller；Linux 走 GitHub Actions |
| Android | Flutter / Dart | GitHub Actions 云端 `flutter build apk` |
| 设备间通讯 | WebSocket + JSON | 桌面端当服务端监听端口，安卓端按填写的 IP:端口连接 |

目录结构：

```
.
├── protocol/          # 跨设备协议（SPEC.md + schema.json，两端实现的唯一依据）
├── desktop/           # Python + PySide6 桌面端（Windows & Linux）
├── android/           # Flutter 安卓端
└── .github/workflows/ # 云端构建（Android APK / Linux AppImage）
```

## 快速开始（桌面端）

```bash
cd desktop
python -m pip install -r requirements.txt   # 主要是 psutil（其余多数已预装）
python main.py
```

小组件默认以「置底无边框窗口」呈现；在设置里可开启「嵌入桌面」（Windows WorkerW 方式）。关闭主窗口会隐藏到系统托盘，右键托盘图标可打开设置 / 退出。

## 功能

- 读取 CPU、GPU、内存、磁盘、电量；无电池 → 插电图标；GPU 读不到 → N/A。
- 可配置告警阈值：电量低/危急、CPU/内存/磁盘过高。
- 充电失速检测：设备插电后一段时间电量未增长 → 再次提醒。
- 桌面端通过系统通知（托盘 toast）推送告警。
- 设备间手动填写 IP:端口配对；断线自动重连；可选 UDP 广播发现辅助首次配对。

## 构建

- **Windows**：`cd desktop && build.bat`（PyInstaller，无需 Visual Studio）。
- **Android**：推送到 GitHub 后由 `.github/workflows/android-apk.yml` 产出 APK（Actions 里下载）。
- **Linux**：`.github/workflows/linux-appimage.yml` 产出 AppImage。

## 说明

- PyInstaller 打包的 exe 偶尔被杀软误报，属常见现象。
- GPU 占用依赖 `nvidia-smi`（NVIDIA）；AMD/集显/安卓暂显示 N/A。
- UDP 广播发现仅在同一二层广播域有效；跨 VLAN 请手动填 IP。
