/// WebSocket server so THIS device can act as a hub: peers connect to it, share
/// their metrics, and receive this device's own metrics in return. Together with
/// [DesktopClient] (outgoing connection), every device both displays itself and
/// the devices connected to it.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'metrics_collector.dart';

class DeviceServer {
  final MetricsCollector collector;
  final int port;
  final String deviceId;
  final String deviceName;
  final int broadcastIntervalSeconds;

  HttpServer? _server;
  Timer? _broadcastTimer;
  final Map<WebSocket, String> _peerIdBySocket = {};
  final Map<String, String> _nameById = {};

  void Function(String id, String name, Map<String, dynamic> data)? onPeerMetrics;
  void Function(String id, String name)? onPeerConnected;
  void Function(String id)? onPeerDisconnected;

  DeviceServer({
    required this.collector,
    required this.port,
    required this.deviceId,
    required this.deviceName,
    this.broadcastIntervalSeconds = 5,
  });

  bool get running => _server != null;

  Future<void> start() async {
    if (running) return;
    try {
      _server = await HttpServer.bind(InternetAddress.anyIPv4, port);
      _server!.listen(_handleRequest, onError: (_) {});
      _broadcastTimer = Timer.periodic(
        Duration(seconds: broadcastIntervalSeconds),
        (_) => _broadcastOwnMetrics(),
      );
    } catch (_) {
      _server = null; // Port in use / no permission -> server stays off.
    }
  }

  Future<void> stop() async {
    _broadcastTimer?.cancel();
    _broadcastTimer = null;
    for (final ws in List.of(_peerIdBySocket.keys)) {
      try {
        await ws.close();
      } catch (_) {}
    }
    _peerIdBySocket.clear();
    try {
      await _server?.close(force: true);
    } catch (_) {}
    _server = null;
  }

  Future<void> _handleRequest(HttpRequest req) async {
    if (WebSocketTransformer.isUpgradeRequest(req)) {
      try {
        final ws = await WebSocketTransformer.upgrade(req);
        _peerIdBySocket[ws] = '';
        ws.listen(
          (raw) => _onData(ws, raw),
          onDone: () => _dropPeer(ws),
          onError: (_) => _dropPeer(ws),
        );
      } catch (_) {}
    } else {
      req.response.statusCode = HttpStatus.notFound;
      await req.response.close();
    }
  }

  void _onData(WebSocket ws, dynamic raw) {
    try {
      final msg = jsonDecode(raw as String) as Map<String, dynamic>;
      final type = msg['type'];
      if (type == 'hello') {
        final id = (msg['device_id'] as String?) ?? 'peer-${ws.hashCode}';
        final name = (msg['device_name'] as String?) ?? id;
        _peerIdBySocket[ws] = id;
        _nameById[id] = name;
        onPeerConnected?.call(id, name);
        ws.add(jsonEncode({
          'type': 'hello_ack',
          'protocol_version': '1.0',
          'device_id': deviceId,
          'device_name': deviceName,
          'platform': 'android',
          'interval_seconds': broadcastIntervalSeconds,
          'timestamp': DateTime.now().millisecondsSinceEpoch / 1000.0,
        }));
        _sendOwnTo(ws);
      } else if (type == 'metrics') {
        final id = (msg['device_id'] as String?) ?? _peerIdBySocket[ws] ?? '';
        if (id.isEmpty) return;
        final data = (msg['data'] as Map?)?.map(
              (k, v) => MapEntry(k.toString(), v),
            ) ??
            <String, dynamic>{};
        onPeerMetrics?.call(id, _nameById[id] ?? id, data.cast<String, dynamic>());
      } else if (type == 'ping') {
        ws.add(jsonEncode({
          'type': 'pong',
          'timestamp': DateTime.now().millisecondsSinceEpoch / 1000.0,
        }));
      }
    } catch (_) {
      // Ignore malformed messages.
    }
  }

  void _dropPeer(WebSocket ws) {
    final id = _peerIdBySocket.remove(ws);
    if (id != null && id.isNotEmpty) {
      // Only notify if no other socket carries the same device id.
      if (!_peerIdBySocket.values.contains(id)) {
        _nameById.remove(id);
        onPeerDisconnected?.call(id);
      }
    }
  }

  Future<void> _broadcastOwnMetrics() async {
    if (!running || _peerIdBySocket.isEmpty) return;
    for (final ws in List.of(_peerIdBySocket.keys)) {
      await _sendOwnTo(ws);
    }
  }

  Future<void> _sendOwnTo(WebSocket ws) async {
    try {
      final payload = await collector.collect();
      ws.add(jsonEncode({
        'type': 'metrics',
        'device_id': deviceId,
        'timestamp': DateTime.now().millisecondsSinceEpoch / 1000.0,
        'data': payload.toDataJson(),
      }));
    } catch (_) {}
  }
}
