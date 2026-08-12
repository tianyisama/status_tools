/// LAN discovery client: broadcasts a small `discover` datagram and collects
/// `discover_ack` replies so the user can pick a desktop instead of typing its
/// IP. Works within the same broadcast domain (fine for a single /22 segment).
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

class DiscoveredDevice {
  final String name;
  final String host;
  final int port;
  final String platform;

  const DiscoveredDevice({
    required this.name,
    required this.host,
    required this.port,
    required this.platform,
  });
}

class DiscoveryScanner {
  /// Broadcasts `discover` on [discoveryPort] and waits [duration] for replies.
  Future<List<DiscoveredDevice>> scan({
    int discoveryPort = 9701,
    Duration duration = const Duration(seconds: 3),
  }) async {
    final found = <String, DiscoveredDevice>{};
    RawDatagramSocket? socket;
    try {
      socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
      socket.broadcastEnabled = true;

      socket.listen((event) {
        if (event != RawSocketEvent.read) return;
        final dg = socket?.receive();
        if (dg == null) return;
        try {
          final msg = jsonDecode(utf8.decode(dg.data, allowMalformed: true));
          if (msg is Map && msg['type'] == 'discover_ack') {
            final host = dg.address.address;
            final port = (msg['service_port'] as num?)?.toInt() ?? 9700;
            final name = (msg['device_name'] as String?) ?? host;
            final platform = (msg['platform'] as String?) ?? '';
            found['$host:$port'] = DiscoveredDevice(
              name: name,
              host: host,
              port: port,
              platform: platform,
            );
          }
        } catch (_) {
          // Ignore malformed replies.
        }
      });

      final payload = utf8.encode(jsonEncode({
        'type': 'discover',
        'protocol_version': '1.0',
      }));

      // Send the broadcast a few times to survive packet loss.
      final broadcast = InternetAddress('255.255.255.255');
      socket.send(payload, broadcast, discoveryPort);
      final deadline = DateTime.now().add(duration);
      while (DateTime.now().isBefore(deadline)) {
        await Future.delayed(const Duration(milliseconds: 700));
        try {
          socket.send(payload, broadcast, discoveryPort);
        } catch (_) {}
      }
      await Future.delayed(const Duration(milliseconds: 300));
    } catch (_) {
      // Discovery is best-effort; manual entry always remains available.
    } finally {
      socket?.close();
    }
    return found.values.toList()
      ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
  }
}

/// Replies to LAN `discover` broadcasts so THIS device can also be found and
/// connected to (peer-to-peer discovery).
class DiscoveryResponder {
  final int discoveryPort;
  final int servicePort;
  final String deviceId;
  final String deviceName;
  final String platform;

  RawDatagramSocket? _socket;

  DiscoveryResponder({
    this.discoveryPort = 9701,
    required this.servicePort,
    required this.deviceId,
    required this.deviceName,
    this.platform = 'android',
  });

  Future<void> start() async {
    try {
      _socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, discoveryPort);
      _socket!.listen((event) {
        if (event != RawSocketEvent.read) return;
        final dg = _socket?.receive();
        if (dg == null) return;
        try {
          final msg = jsonDecode(utf8.decode(dg.data, allowMalformed: true));
          if (msg is Map && msg['type'] == 'discover') {
            final ack = utf8.encode(jsonEncode({
              'type': 'discover_ack',
              'protocol_version': '1.0',
              'device_id': deviceId,
              'device_name': deviceName,
              'platform': platform,
              'service_port': servicePort,
            }));
            _socket?.send(ack, dg.address, dg.port);
          }
        } catch (_) {}
      });
    } catch (_) {
      // Discovery is best-effort.
    }
  }

  void stop() {
    _socket?.close();
    _socket = null;
  }
}
