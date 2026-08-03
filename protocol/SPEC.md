# status_tools 跨设备协议 v1.0

桌面端（Python）与安卓端（Dart）各自实现本协议。本文件与 `schema.json` 是唯一依据；两端结构必须一致。

## 基本约定

- 传输：WebSocket，消息为 **单行 JSON 文本**。
- 每条消息是 JSON 对象，必有顶层字符串字段 `type`。
- 握手携带 `protocol_version`（形如 `"1.0"`）。**主版本不一致即拒绝连接**；次版本差异向下兼容。未知 `type` 一律忽略（前向兼容）。
- 时间戳：Unix 秒（float，UTC）。
- 百分比：`0.0`–`100.0` 的 float。
- 读不到的字段一律为 `null`，**不要省略**，保证两端结构一致。
- 桌面端为**服务端**，监听 `service_port`（默认 9700）；安卓端为**客户端**，按用户填写的 `IP:service_port` 连接并周期上报。
- 发现（可选）走独立 **UDP** 端口 `discovery_port`（默认 9701），见文末。

## 消息类型

### `hello`（客户端 → 服务端，连接建立后立即发送）

```json
{
  "type": "hello",
  "protocol_version": "1.0",
  "device_id": "android-pixel7-abc123",
  "device_name": "Pixel 7",
  "platform": "android",
  "app_version": "1.0.0",
  "timestamp": 1722681600.0
}
```

### `hello_ack`（服务端 → 客户端）

```json
{
  "type": "hello_ack",
  "protocol_version": "1.0",
  "device_id": "desktop-win11-xyz789",
  "device_name": "DESKTOP-RTX4080",
  "platform": "windows",
  "interval_seconds": 5,
  "timestamp": 1722681600.1
}
```

`interval_seconds` 指示客户端上报周期。

### `metrics`（周期性遥测，双向通用）

```json
{
  "type": "metrics",
  "device_id": "android-pixel7-abc123",
  "timestamp": 1722681605.0,
  "data": {
    "cpu":     { "percent": 34.2, "core_count": 8 },
    "gpu":     { "available": false, "percent": null, "memory_used_mb": null, "memory_total_mb": null, "temperature_c": null },
    "memory":  { "percent": 61.5, "used_mb": 4820, "total_mb": 7864 },
    "disk":    { "percent": 72.3, "used_gb": 92.1, "total_gb": 127.4 },
    "battery": { "present": true, "percent": 28.0, "plugged": false, "status": "discharging" }
  }
}
```

- 无电池的台式机：`battery = { "present": false, "percent": null, "plugged": null, "status": "no_battery" }` → UI 显示**插电图标**。
- 有电池并接通电源：`plugged = true`，`status` 取 `"charging"` 或 `"full"`。
- GPU 可用（NVIDIA 桌面）：`available=true` 且各字段为数值；不可用（AMD/集显/安卓）：`available=false` 且其余为 `null` → UI 显示 N/A。

### `ping` / `pong`（保活）

```json
{ "type": "ping", "timestamp": 1722681620.0 }
{ "type": "pong", "timestamp": 1722681620.1 }
```

任意一方都可发起 `ping`，对端回 `pong`。

### `config`（服务端 → 客户端，可选）

桌面端把告警阈值下发给手机，便于本机也提示。

```json
{
  "type": "config",
  "thresholds": {
    "battery_low_percent": 30,
    "battery_critical_percent": 15,
    "cpu_high_percent": 95,
    "memory_high_percent": 90,
    "disk_high_percent": 90
  },
  "charging_stall_minutes": 10,
  "timestamp": 1722681615.0
}
```

## 设备配对 / 重连

- **主路径**：客户端保存服务端 `IP:service_port`；断线后按指数退避（1s→2s→4s→…，封顶 ~30s）重连。
- **发现（可选，UDP）**：客户端向 `255.255.255.255:discovery_port` 广播
  `{ "type": "discover", "protocol_version": "1.0" }`；服务端常驻 UDP 监听并单播回应：

```json
{
  "type": "discover_ack",
  "protocol_version": "1.0",
  "device_id": "desktop-win11-xyz789",
  "device_name": "DESKTOP-RTX4080",
  "platform": "windows",
  "service_port": 9700
}
```

`service_port` 随应答带回，客户端无需预先知道。广播仅在同一二层广播域有效；跨 VLAN 请手动填 IP。

## 字段语义速查

| 路径 | 类型 | 说明 |
|---|---|---|
| `data.cpu.percent` | float | CPU 占用百分比 |
| `data.cpu.core_count` | int | 逻辑核心数 |
| `data.gpu.available` | bool | 是否能读到 GPU |
| `data.gpu.percent` | float? | GPU 占用百分比 |
| `data.gpu.memory_used_mb` / `memory_total_mb` | int? | 显存 MB |
| `data.gpu.temperature_c` | float? | GPU 温度 ℃ |
| `data.memory.percent` | float | 内存占用百分比 |
| `data.memory.used_mb` / `total_mb` | int | 内存 MB |
| `data.disk.percent` | float | 系统盘占用百分比 |
| `data.disk.used_gb` / `total_gb` | float | 系统盘 GB |
| `data.battery.present` | bool | 是否有电池 |
| `data.battery.percent` | float? | 电量百分比 |
| `data.battery.plugged` | bool? | 是否接通电源 |
| `data.battery.status` | string | `charging` / `discharging` / `full` / `no_battery` |
