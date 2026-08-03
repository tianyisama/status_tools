/// Main screen: shows the phone's own metrics and the connection status to the
/// desktop, with access to settings.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../models/metrics.dart';
import '../services/metrics_collector.dart';
import '../services/websocket_client.dart';
import '../utils/config.dart';
import '../widgets/metric_card.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  final MetricsCollector collector;
  final DesktopClient client;
  final AppConfig config;

  const HomeScreen({super.key, required this.collector, required this.client, required this.config});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Timer? _refreshTimer;
  MetricsPayload? _metrics;
  ConnState _conn = ConnState.disconnected;

  @override
  void initState() {
    super.initState();
    _conn = widget.client.state;
    widget.client.onStateChanged = (s) {
      if (mounted) setState(() => _conn = s);
    };
    _refreshTimer = Timer.periodic(const Duration(seconds: 2), (_) => _refresh());
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final m = await widget.collector.collect();
      if (mounted) setState(() => _metrics = m);
    } catch (_) {}
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    widget.client.onStateChanged = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final m = _metrics;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Status Tools'),
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
        ],
      ),
      body: Column(
        children: [
          _ConnectionBanner(state: _conn, config: widget.config, error: widget.client.lastError),
          Expanded(
            child: m == null
                ? const Center(child: CircularProgressIndicator())
                : ListView(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    children: [
                      MetricCard(
                        icon: Icons.memory,
                        label: 'CPU',
                        value: '${m.cpu.percent.toStringAsFixed(0)}%',
                        detail: '${m.cpu.coreCount} 核',
                        percent: m.cpu.percent,
                      ),
                      MetricCard(
                        icon: Icons.videogame_asset,
                        label: 'GPU',
                        value: 'N/A',
                        detail: '安卓不可读',
                        percent: null,
                      ),
                      MetricCard(
                        icon: Icons.sd_storage,
                        label: '内存',
                        value: '${m.memory.percent.toStringAsFixed(0)}%',
                        detail:
                            '${(m.memory.usedMb / 1024).toStringAsFixed(1)}/${(m.memory.totalMb / 1024).toStringAsFixed(1)} GB',
                        percent: m.memory.percent,
                      ),
                      MetricCard(
                        icon: Icons.storage,
                        label: '存储',
                        value: '${m.disk.percent.toStringAsFixed(0)}%',
                        detail:
                            '${m.disk.usedGb.toStringAsFixed(0)}/${m.disk.totalGb.toStringAsFixed(0)} GB',
                        percent: m.disk.percent,
                      ),
                      _batteryCard(m.battery),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _batteryCard(BatteryMetrics b) {
    if (!b.present) {
      return const MetricCard(icon: Icons.power, label: '电源', value: 'AC', detail: '未检测到电池', percent: null);
    }
    final pct = b.percent ?? 0.0;
    final isCharging = b.plugged == true;
    final statusText = switch (b.status) {
      'charging' => '充电中',
      'full' => '已充满',
      'discharging' => '放电中',
      _ => '',
    };
    Color color;
    if (pct <= 15) {
      color = Colors.redAccent;
    } else if (pct <= 30) {
      color = Colors.orangeAccent;
    } else {
      color = Colors.greenAccent;
    }
    return MetricCard(
      icon: isCharging ? Icons.bolt : Icons.battery_std,
      label: '电量',
      value: '${pct.toStringAsFixed(0)}%',
      detail: statusText,
      percent: pct,
      color: color,
    );
  }
}

class _ConnectionBanner extends StatelessWidget {
  final ConnState state;
  final AppConfig config;
  final String? error;

  const _ConnectionBanner({required this.state, required this.config, this.error});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final (icon, text, color) = switch (state) {
      ConnState.connected => (Icons.cloud_done, '已连接到 ${config.host}:${config.port}', Colors.greenAccent),
      ConnState.connecting => (Icons.sync, '正在连接 ${config.host}:${config.port}…', Colors.orangeAccent),
      ConnState.disconnected => (
          Icons.cloud_off,
          config.hasAddress ? '未连接${error != null ? '（$error）' : ''}' : '未配置桌面地址（右上角设置）',
          cs.outline,
        ),
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: color.withValues(alpha: 0.12),
      child: Row(
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: TextStyle(fontSize: 13, color: color))),
        ],
      ),
    );
  }
}
