import 'package:flutter/material.dart';

import 'screens/home_screen.dart';
import 'services/metrics_collector.dart';
import 'services/websocket_client.dart';
import 'utils/config.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final collector = MetricsCollector();
  await collector.warmUp();

  final config = await AppConfig.load();
  final client = DesktopClient(collector: collector, config: config);

  // Auto-reconnect to the saved address on launch (primary pairing path).
  if (config.hasAddress) {
    client.start();
  }

  runApp(StatusToolsApp(collector: collector, client: client, config: config));
}

class StatusToolsApp extends StatelessWidget {
  final MetricsCollector collector;
  final DesktopClient client;
  final AppConfig config;

  const StatusToolsApp({super.key, required this.collector, required this.client, required this.config});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Status Tools',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.dark,
      darkTheme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6096FF), brightness: Brightness.dark),
      ),
      home: HomeScreen(collector: collector, client: client, config: config),
    );
  }
}
