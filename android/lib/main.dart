import 'package:flutter/material.dart';

import 'screens/home_screen.dart';
import 'services/device_server.dart';
import 'services/discovery.dart';
import 'services/metrics_collector.dart';
import 'services/websocket_client.dart';
import 'utils/config.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final collector = MetricsCollector();
  await collector.warmUp();

  final config = await AppConfig.load();
  final client = DesktopClient(collector: collector, config: config);

  // This device can also act as a hub: peers may connect to it on this port.
  final server = DeviceServer(
    collector: collector,
    port: 9700,
    deviceId: collector.deviceId,
    deviceName: collector.deviceName,
  );
  await server.start();

  // Be discoverable on the LAN so other devices can find and connect to us.
  final discoveryResponder = DiscoveryResponder(
    servicePort: 9700,
    deviceId: collector.deviceId,
    deviceName: collector.deviceName,
  );
  await discoveryResponder.start();

  // Auto-reconnect to the saved address on launch (primary pairing path).
  if (config.hasAddress) {
    client.start();
  }

  runApp(StatusToolsApp(collector: collector, client: client, config: config, server: server));
}

class StatusToolsApp extends StatelessWidget {
  final MetricsCollector collector;
  final DesktopClient client;
  final AppConfig config;
  final DeviceServer server;

  const StatusToolsApp({
    super.key,
    required this.collector,
    required this.client,
    required this.config,
    required this.server,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Status Tools',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.dark,
      darkTheme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6C8CFF), brightness: Brightness.dark),
        appBarTheme: const AppBarTheme(centerTitle: false, elevation: 0, scrolledUnderElevation: 2),
        snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
        pageTransitionsTheme: const PageTransitionsTheme(builders: {
          TargetPlatform.android: ZoomPageTransitionsBuilder(),
        }),
      ),
      home: HomeScreen(collector: collector, client: client, config: config, server: server),
    );
  }
}
