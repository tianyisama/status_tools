/// Settings: enter the desktop's IP:port (manual pairing) or auto-scan the LAN,
/// then save and connect.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/discovery.dart';
import '../services/websocket_client.dart';
import '../utils/config.dart';

class SettingsScreen extends StatefulWidget {
  final DesktopClient client;
  final AppConfig config;

  const SettingsScreen({super.key, required this.client, required this.config});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _hostCtrl;
  late final TextEditingController _portCtrl;
  late final TextEditingController _intervalCtrl;
  final _formKey = GlobalKey<FormState>();
  bool _saving = false;
  bool _scanning = false;

  @override
  void initState() {
    super.initState();
    _hostCtrl = TextEditingController(text: widget.config.host);
    _portCtrl = TextEditingController(text: widget.config.port.toString());
    _intervalCtrl = TextEditingController(text: widget.config.intervalSeconds.toString());
  }

  @override
  void dispose() {
    _hostCtrl.dispose();
    _portCtrl.dispose();
    _intervalCtrl.dispose();
    super.dispose();
  }

  Future<void> _saveAndConnect() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() => _saving = true);

    final cfg = AppConfig(
      host: _hostCtrl.text.trim(),
      port: int.tryParse(_portCtrl.text.trim()) ?? 9700,
      intervalSeconds: int.tryParse(_intervalCtrl.text.trim()) ?? 5,
    );
    await cfg.save();
    widget.client.updateConfig(cfg);

    if (mounted) {
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已保存并尝试连接 ${cfg.host}:${cfg.port}')),
      );
    }
  }

  Future<void> _scan() async {
    setState(() => _scanning = true);
    final devices = await DiscoveryScanner().scan();
    if (!mounted) return;
    setState(() => _scanning = false);
    _showDevices(devices);
  }

  void _showDevices(List<DiscoveredDevice> devices) {
    final cs = Theme.of(context).colorScheme;
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      backgroundColor: cs.surface,
      builder: (sheetContext) {
        if (devices.isEmpty) {
          return Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.radar_rounded, size: 40, color: cs.outline),
                const SizedBox(height: 12),
                const Text('没有发现设备', style: TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                Text(
                  '请确认电脑端已打开并且和手机在同一局域网；也可以手动填写 IP。',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 13, color: cs.outline),
                ),
              ],
            ),
          );
        }
        return ListView(
          shrinkWrap: true,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
              child: Text('发现 ${devices.length} 台设备',
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
            ),
            ...devices.map(
              (d) => ListTile(
                leading: CircleAvatar(child: Icon(d.platform.contains('windows') ? Icons.desktop_windows : Icons.device_hub)),
                title: Text(d.name),
                subtitle: Text('${d.host}:${d.port}'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  _hostCtrl.text = d.host;
                  _portCtrl.text = d.port.toString();
                  Navigator.of(sheetContext).pop();
                  setState(() {});
                },
              ),
            ),
            const SizedBox(height: 12),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('连接设置')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Scan card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [cs.primary.withValues(alpha: 0.16), cs.tertiary.withValues(alpha: 0.10)]),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: cs.primary.withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  Icon(Icons.radar_rounded, color: cs.primary),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Text(
                      '自动搜索局域网里的电脑',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                  FilledButton.tonalIcon(
                    onPressed: _scanning ? null : _scan,
                    icon: _scanning
                        ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.search),
                    label: Text(_scanning ? '搜索中' : '扫描'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            Text('或手动填写', style: TextStyle(fontSize: 13, color: cs.outline)),
            const SizedBox(height: 10),
            TextFormField(
              controller: _hostCtrl,
              decoration: const InputDecoration(
                labelText: '桌面 IP 地址',
                hintText: '例如 192.168.1.10',
                prefixIcon: Icon(Icons.lan_outlined),
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.text,
              validator: (v) {
                final s = (v ?? '').trim();
                if (s.isEmpty) return '请输入 IP 地址';
                final ip = Uri.tryParse('http://$s');
                if (ip == null || ip.host.isEmpty) return 'IP 地址格式不正确';
                return null;
              },
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _portCtrl,
                    decoration: const InputDecoration(
                      labelText: '端口',
                      hintText: '9700',
                      prefixIcon: Icon(Icons.numbers_rounded),
                      border: OutlineInputBorder(),
                    ),
                    keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    validator: (v) {
                      final p = int.tryParse((v ?? '').trim());
                      if (p == null || p < 1 || p > 65535) return '端口 1–65535';
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _intervalCtrl,
                    decoration: const InputDecoration(
                      labelText: '间隔(秒)',
                      prefixIcon: Icon(Icons.timer_outlined),
                      border: OutlineInputBorder(),
                    ),
                    keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    validator: (v) {
                      final i = int.tryParse((v ?? '').trim());
                      if (i == null || i < 1 || i > 300) return '1–300';
                      return null;
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 28),
            FilledButton.icon(
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(50)),
              onPressed: _saving ? null : _saveAndConnect,
              icon: _saving
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.link_rounded),
              label: Text(_saving ? '保存中…' : '保存并连接', style: const TextStyle(fontSize: 15)),
            ),
          ],
        ),
      ),
    );
  }
}
