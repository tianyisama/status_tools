/// Collects the phone's own metrics.
///
/// Battery comes from `battery_plus`; CPU / memory / storage come from the
/// Kotlin platform channel (`statustools/metrics`), since Dart cannot read
/// `/proc`. GPU is not readable on Android without root -> always N/A.
library;

import 'dart:io';

import 'package:battery_plus/battery_plus.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/services.dart';

import '../models/metrics.dart';

class MetricsCollector {
  static const _channel = MethodChannel('statustools/metrics');
  final Battery _battery = Battery();
  final DeviceInfoPlugin _deviceInfo = DeviceInfoPlugin();

  String? cachedDeviceId;
  String? cachedDeviceName;

  Future<void> warmUp() async {
    try {
      final info = await _deviceInfo.androidInfo;
      cachedDeviceName = '${info.brand} ${info.model}';
      cachedDeviceId = 'android-${info.id.toLowerCase()}';
    } catch (_) {
      cachedDeviceName = Platform.localHostname;
      cachedDeviceId = 'android-${Platform.localHostname}';
    }
  }

  String get deviceId => cachedDeviceId ?? 'android-unknown';
  String get deviceName => cachedDeviceName ?? 'Android';

  Future<MetricsPayload> collect() async {
    final cpu = await _readCpu();
    final mem = await _readMemory();
    final disk = await _readStorage();
    final battery = await _readBattery();
    return MetricsPayload(
      cpu: cpu,
      gpu: GpuMetrics.unavailable(),
      memory: mem,
      disk: disk,
      battery: battery,
    );
  }

  Future<CpuMetrics> _readCpu() async {
    try {
      final percent = await _channel.invokeMethod<double>('getCpuPercent');
      return CpuMetrics(percent: percent ?? 0.0, coreCount: Platform.numberOfProcessors);
    } catch (_) {
      return CpuMetrics(percent: 0.0, coreCount: Platform.numberOfProcessors);
    }
  }

  Future<MemoryMetrics> _readMemory() async {
    try {
      final map = await _channel.invokeMethod<Map<dynamic, dynamic>>('getMemoryInfo');
      if (map == null) throw Exception('null');
      return MemoryMetrics(
        percent: (map['percent'] as num?)?.toDouble() ?? 0.0,
        usedMb: (map['usedMb'] as num?)?.toInt() ?? 0,
        totalMb: (map['totalMb'] as num?)?.toInt() ?? 0,
      );
    } catch (_) {
      return MemoryMetrics(percent: 0.0, usedMb: 0, totalMb: 0);
    }
  }

  Future<DiskMetrics> _readStorage() async {
    try {
      final map = await _channel.invokeMethod<Map<dynamic, dynamic>>('getStorageInfo');
      if (map == null) throw Exception('null');
      return DiskMetrics(
        percent: (map['percent'] as num?)?.toDouble() ?? 0.0,
        usedGb: (map['usedGb'] as num?)?.toDouble() ?? 0.0,
        totalGb: (map['totalGb'] as num?)?.toDouble() ?? 0.0,
      );
    } catch (_) {
      return DiskMetrics(percent: 0.0, usedGb: 0.0, totalGb: 0.0);
    }
  }

  Future<BatteryMetrics> _readBattery() async {
    try {
      final level = await _battery.batteryLevel;
      final state = await _battery.batteryState;
      final plugged =
          state == BatteryState.charging || state == BatteryState.full;
      final status = switch (state) {
        BatteryState.charging => 'charging',
        BatteryState.full => 'full',
        BatteryState.discharging => 'discharging',
        _ => 'unknown',
      };
      double? temp;
      try {
        final t = await _channel.invokeMethod<double>('getBatteryTemp');
        if (t != null && t > 0) temp = t;
      } catch (_) {
        temp = null;
      }
      return BatteryMetrics(
        present: true,
        percent: level.toDouble(),
        plugged: plugged,
        status: status,
        temperatureC: temp,
      );
    } catch (_) {
      return BatteryMetrics(present: true, percent: null, plugged: null, status: 'unknown');
    }
  }
}
