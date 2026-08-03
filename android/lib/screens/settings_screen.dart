/// Settings: enter the desktop's IP:port (manual pairing), save, and connect.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('连接设置')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              '在电脑端「设置 → 网络」里可以看到本机 IP。把它和端口填到下面，手机就会把指标推送给电脑。',
              style: TextStyle(fontSize: 13, color: Colors.white70),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _hostCtrl,
              decoration: const InputDecoration(
                labelText: '桌面 IP 地址',
                hintText: '例如 192.168.1.10',
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
            TextFormField(
              controller: _portCtrl,
              decoration: const InputDecoration(
                labelText: '端口',
                hintText: '9700',
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              validator: (v) {
                final p = int.tryParse((v ?? '').trim());
                if (p == null || p < 1 || p > 65535) return '端口需在 1–65535 之间';
                return null;
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _intervalCtrl,
              decoration: const InputDecoration(
                labelText: '上报间隔（秒）',
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              validator: (v) {
                final i = int.tryParse((v ?? '').trim());
                if (i == null || i < 1 || i > 300) return '间隔需在 1–300 秒之间';
                return null;
              },
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _saving ? null : _saveAndConnect,
              icon: _saving
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.link),
              label: const Text('保存并连接'),
            ),
          ],
        ),
      ),
    );
  }
}
