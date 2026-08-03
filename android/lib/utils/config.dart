/// Persisted client settings (desktop address, report interval) via SharedPreferences.
library;

import 'package:shared_preferences/shared_preferences.dart';

class AppConfig {
  static const _kHost = 'desktop_host';
  static const _kPort = 'desktop_port';
  static const _kInterval = 'report_interval_seconds';

  String host;
  int port;
  int intervalSeconds;

  AppConfig({this.host = '', this.port = 9700, this.intervalSeconds = 5});

  bool get hasAddress => host.trim().isNotEmpty && port > 0;

  static Future<AppConfig> load() async {
    final prefs = await SharedPreferences.getInstance();
    return AppConfig(
      host: prefs.getString(_kHost) ?? '',
      port: prefs.getInt(_kPort) ?? 9700,
      intervalSeconds: prefs.getInt(_kInterval) ?? 5,
    );
  }

  Future<void> save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kHost, host);
    await prefs.setInt(_kPort, port);
    await prefs.setInt(_kInterval, intervalSeconds);
  }
}
