/// Main screen: animated ring gauges for CPU / memory / battery plus tiles for
/// storage and GPU, with a live connection status chip.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../models/metrics.dart';
import '../services/device_server.dart';
import '../services/metrics_collector.dart';
import '../services/websocket_client.dart';
import '../utils/config.dart';
import '../widgets/ring_gauge.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  final MetricsCollector collector;
  final DesktopClient client;
  final AppConfig config;
  final DeviceServer? server;

  const HomeScreen({
    super.key,
    required this.collector,
    required this.client,
    required this.config,
    this.server,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _Peer {
  final String name;
  final Map<String, dynamic> data;
  _Peer(this.name, this.data);
}

class _HomeScreenState extends State<HomeScreen> {
  Timer? _timer;
  MetricsPayload? _m;
  ConnState _conn = ConnState.disconnected;
  final Map<String, _Peer> _peers = {};

  @override
  void initState() {
    super.initState();
    _conn = widget.client.state;
    widget.client.onStateChanged = (s) {
      if (mounted) setState(() => _conn = s);
    };
    widget.client.onPeerMetrics = (id, name, data) {
      if (mounted) setState(() => _peers[id] = _Peer(name, data));
    };
    widget.server?.onPeerMetrics = (id, name, data) {
      if (mounted) setState(() => _peers[id] = _Peer(name, data));
    };
    widget.server?.onPeerDisconnected = (id) {
      if (mounted) setState(() => _peers.remove(id));
    };
    _timer = Timer.periodic(const Duration(seconds: 2), (_) => _refresh());
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final m = await widget.collector.collect();
      if (mounted) setState(() => _m = m);
    } catch (_) {}
  }

  @override
  void dispose() {
    _timer?.cancel();
    widget.client.onStateChanged = null;
    widget.client.onPeerMetrics = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final m = _m;
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              width: 30,
              height: 30,
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [cs.primary, cs.tertiary]),
                borderRadius: BorderRadius.circular(9),
              ),
              child: Icon(Icons.monitor_heart, size: 18, color: cs.onPrimary),
            ),
            const SizedBox(width: 10),
            const Text('Status Tools', style: TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: '设置',
            onPressed: () async {
              await Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => SettingsScreen(client: widget.client, config: widget.config),
                ),
              );
              if (mounted) setState(() => _conn = widget.client.state);
            },
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: SafeArea(
        child: m == null
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                children: [
                  _ConnectionChip(state: _conn, config: widget.config, error: widget.client.lastError),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: RingGauge(
                          value: m.cpu.percent,
                          label: 'CPU',
                          icon: Icons.memory,
                          caption: m.cpu.temperatureC != null
                              ? '${m.cpu.temperatureC!.toStringAsFixed(0)}°C · ${m.cpu.coreCount} 核'
                              : '${m.cpu.coreCount} 核',
                        ),
                      ),
                      Expanded(
                        child: RingGauge(
                          value: m.memory.percent,
                          label: '内存',
                          icon: Icons.sd_storage,
                          caption:
                              '${(m.memory.usedMb / 1024).toStringAsFixed(1)}/${(m.memory.totalMb / 1024).toStringAsFixed(1)} GB',
                        ),
                      ),
                      Expanded(child: _batteryGauge(m.battery)),
                    ],
                  ),
                  const SizedBox(height: 18),
                  _StorageTile(disk: m.disk),
                  if (_peers.isNotEmpty) ...[
                    const SizedBox(height: 22),
                    Padding(
                      padding: const EdgeInsets.only(left: 4, bottom: 8),
                      child: Text(
                        '已连接设备（${_peers.length}）',
                        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
                      ),
                    ),
                    ..._peers.values.map((p) => Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: _PeerCard(peer: p),
                        )),
                  ],
                ],
              ),
      ),
    );
  }

  Widget _batteryGauge(BatteryMetrics b) {
    final pct = b.percent ?? 0.0;
    final charging = b.plugged == true;
    Color color;
    if (pct <= 15) {
      color = Colors.redAccent;
    } else if (pct <= 30) {
      color = Colors.amberAccent;
    } else {
      color = Colors.greenAccent;
    }
    final bits = <String>[];
    if (b.temperatureC != null && b.temperatureC! > 0) {
      bits.add('${b.temperatureC!.toStringAsFixed(1)}°C');
    }
    bits.add(switch (b.status) {
      'charging' => '充电中',
      'full' => '已充满',
      'discharging' => '放电中',
      _ => '',
    });
    return RingGauge(
      value: pct,
      label: '电量',
      icon: charging ? Icons.bolt : Icons.battery_std,
      color: color,
      caption: bits.where((s) => s.isNotEmpty).join(' · '),
    );
  }
}

class _ConnectionChip extends StatelessWidget {
  final ConnState state;
  final AppConfig config;
  final String? error;

  const _ConnectionChip({required this.state, required this.config, this.error});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final (icon, text, color) = switch (state) {
      ConnState.connected => (Icons.cloud_done_rounded, '已连接 ${config.host}:${config.port}', Colors.greenAccent),
      ConnState.connecting => (Icons.sync_rounded, '正在连接 ${config.host}:${config.port}…', Colors.amberAccent),
      ConnState.disconnected => (
          Icons.cloud_off_rounded,
          config.hasAddress ? '未连接${error != null ? '' : '（点右上角设置）'}' : '未配置桌面地址',
          cs.outline,
        ),
    };
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          Icon(icon, size: 20, color: color),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: TextStyle(fontSize: 13.5, color: color, fontWeight: FontWeight.w600))),
        ],
      ),
    );
  }
}

class _StorageTile extends StatelessWidget {
  final DiskMetrics disk;
  const _StorageTile({required this.disk});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final color = disk.percent >= 90 ? Colors.redAccent : (disk.percent >= 75 ? Colors.amberAccent : cs.primary);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.storage_rounded, size: 20, color: color),
              const SizedBox(width: 10),
              const Expanded(child: Text('存储', style: TextStyle(fontWeight: FontWeight.w600))),
              Text('${disk.percent.toStringAsFixed(0)}%',
                  style: TextStyle(fontWeight: FontWeight.w700, color: color)),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(5),
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: (disk.percent / 100).clamp(0.0, 1.0)),
              duration: const Duration(milliseconds: 700),
              curve: Curves.easeOutCubic,
              builder: (context, v, _) => LinearProgressIndicator(
                value: v,
                minHeight: 8,
                backgroundColor: cs.surfaceContainerHighest,
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '已用 ${disk.usedGb.toStringAsFixed(0)} / ${disk.totalGb.toStringAsFixed(0)} GB',
            style: TextStyle(fontSize: 12, color: cs.outline),
          ),
        ],
      ),
    );
  }
}

class _PeerCard extends StatelessWidget {
  final _Peer peer;
  const _PeerCard({required this.peer});

  Color _battColor(double pct) {
    if (pct <= 15) return Colors.redAccent;
    if (pct <= 30) return Colors.amberAccent;
    return Colors.greenAccent;
  }

  Widget _chip(IconData icon, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.13),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: color),
          const SizedBox(width: 3),
          Text(text, style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final data = peer.data;
    final battery = (data['battery'] as Map?) ?? const {};
    final cpu = (data['cpu'] as Map?) ?? const {};
    final mem = (data['memory'] as Map?) ?? const {};

    final present = battery['present'] == true;
    final pct = (battery['percent'] as num?)?.toDouble();
    final plugged = battery['plugged'] == true;
    final cpuPct = (cpu['percent'] as num?)?.toDouble();
    final memPct = (mem['percent'] as num?)?.toDouble();
    final cpuTemp = (cpu['temperature_c'] as num?)?.toDouble();

    final chips = <Widget>[];
    if (present && pct != null) {
      chips.add(_chip(plugged ? Icons.bolt : Icons.battery_std, '${pct.toInt()}%', _battColor(pct)));
    } else {
      chips.add(_chip(Icons.power, 'AC', cs.primary));
    }
    if (cpuPct != null) {
      chips.add(_chip(
        Icons.memory,
        cpuTemp != null ? '${cpuPct.toInt()}%·${cpuTemp.toInt()}°' : '${cpuPct.toInt()}%',
        cs.primary,
      ));
    }
    if (memPct != null) chips.add(_chip(Icons.sd_storage, '${memPct.toInt()}%', cs.tertiary));

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: cs.primary.withValues(alpha: 0.15),
            child: Icon(Icons.devices_other_rounded, color: cs.primary, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              peer.name,
              style: const TextStyle(fontWeight: FontWeight.w600),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Wrap(spacing: 6, runSpacing: 4, children: chips),
        ],
      ),
    );
  }
}
