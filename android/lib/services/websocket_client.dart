/// WebSocket client: connects to the desktop server, sends `hello`, then pushes
/// `metrics` on an interval. Reconnects with exponential backoff to the saved
/// address (the primary pairing path on a large LAN).
library;

import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../utils/config.dart';
import 'metrics_collector.dart';

enum ConnState { disconnected, connecting, connected }

class DesktopClient {
  final MetricsCollector collector;
  AppConfig config;

  WebSocketChannel? _channel;
  Timer? _sendTimer;
  Timer? _reconnectTimer;
  bool _shouldRun = false;
  int _backoffSeconds = 1;

  ConnState state = ConnState.disconnected;
  String? lastError;
  void Function(ConnState state)? onStateChanged;

  /// Called when a connected peer (e.g. the desktop) sends its own metrics, so
  /// this device can display the peer as a remote device (peer-to-peer display).
  void Function(String id, String name, Map<String, dynamic> data)? onPeerMetrics;

  String? _peerName;

  static const int _maxBackoffSeconds = 30;
  static const String _protocolVersion = '1.0';

  DesktopClient({required this.collector, required this.config});

  void start() {
    _shouldRun = true;
    _backoffSeconds = 1;
    _connect();
  }

  void stop() {
    _shouldRun = false;
    _sendTimer?.cancel();
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
    _setState(ConnState.disconnected);
  }

  void updateConfig(AppConfig newConfig) {
    config = newConfig;
    // Restart the connection with the new address.
    stop();
    start();
  }

  void _setState(ConnState s) {
    state = s;
    onStateChanged?.call(s);
  }

  void _connect() {
    if (!_shouldRun) return;
    if (!config.hasAddress) {
      lastError = '未配置桌面地址';
      _setState(ConnState.disconnected);
      return;
    }

    _setState(ConnState.connecting);
    final uri = Uri.parse('ws://${config.host.trim()}:${config.port}');

    try {
      final channel = WebSocketChannel.connect(uri);
      _channel = channel;

      channel.ready.timeout(const Duration(seconds: 8)).then((_) {
        _backoffSeconds = 1;
        _setState(ConnState.connected);
        _sendHello();
        _startSending();
      }).catchError((Object err) {
        _handleFailure('$err');
      });

      channel.stream.listen(
        _onMessage,
        onError: (Object err) => _handleFailure('$err'),
        onDone: () => _handleFailure('connection closed'),
      );
    } catch (e) {
      _handleFailure('$e');
    }
  }

  void _onMessage(dynamic raw) {
    try {
      final msg = jsonDecode(raw as String) as Map<String, dynamic>;
      final type = msg['type'];
      if (type == 'hello_ack') {
        _peerName = msg['device_name'] as String?;
        final interval = (msg['interval_seconds'] as num?)?.toInt();
        if (interval != null && interval >= 1) {
          config.intervalSeconds = interval;
          _startSending(); // apply server-requested cadence
        }
      } else if (type == 'metrics') {
        // A peer is sharing its own metrics -> surface it as a remote device.
        final id = (msg['device_id'] as String?) ?? '';
        final data = (msg['data'] as Map?)?.map(
              (k, v) => MapEntry(k.toString(), v),
            ) ??
            <String, dynamic>{};
        if (id.isNotEmpty) {
          onPeerMetrics?.call(id, _peerName ?? id, data.cast<String, dynamic>());
        }
      }
    } catch (_) {
      // Ignore malformed messages.
    }
  }

  void _sendHello() {
    final hello = {
      'type': 'hello',
      'protocol_version': _protocolVersion,
      'device_id': collector.deviceId,
      'device_name': collector.deviceName,
      'platform': 'android',
      'app_version': '1.0.0',
      'timestamp': DateTime.now().millisecondsSinceEpoch / 1000.0,
    };
    _channel?.sink.add(jsonEncode(hello));
  }

  void _startSending() {
    _sendTimer?.cancel();
    _sendTimer = Timer.periodic(Duration(seconds: config.intervalSeconds), (_) => _sendMetrics());
    _sendMetrics(); // send one immediately
  }

  Future<void> _sendMetrics() async {
    if (state != ConnState.connected) return;
    try {
      final payload = await collector.collect();
      final msg = {
        'type': 'metrics',
        'device_id': collector.deviceId,
        'timestamp': DateTime.now().millisecondsSinceEpoch / 1000.0,
        'data': payload.toDataJson(),
      };
      _channel?.sink.add(jsonEncode(msg));
    } catch (_) {
      // Transient collection/send failure; retry on next tick.
    }
  }

  void _handleFailure(String err) {
    lastError = err;
    _sendTimer?.cancel();
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;

    if (!_shouldRun) {
      _setState(ConnState.disconnected);
      return;
    }

    _setState(ConnState.disconnected);
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(Duration(seconds: _backoffSeconds), _connect);
    _backoffSeconds = (_backoffSeconds * 2).clamp(1, _maxBackoffSeconds);
  }
}
