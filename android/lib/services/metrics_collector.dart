/// Collects the phone's own metrics.
///
/// Battery comes from `battery_plus`; memory / storage / battery temperature
/// come from the Kotlin platform channel (`statustools/metrics`). CPU is read
/// directly from `/proc/stat` with `dart:io` (no channel round-trip): a
/// snapshot-delta over the app's own refresh cadence, like psutil on desktop.
/// GPU is not readable on Android without root -> always N/A.
library;

import 'dart:convert' show utf8;
import 'dart:io';
import 'dart:typed_data';

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

  // Previous /proc/stat snapshot, used to compute a delta between refreshes.
  ({int total, int idle})? _prevCpuSample;

  Future<CpuMetrics> _readCpu() async {
    final coreCount = Platform.numberOfProcessors;

    double? computePercent(({int total, int idle}) a, ({int total, int idle}) b) {
      final dTotal = b.total - a.total;
      final dIdle = b.idle - a.idle;
      if (dTotal <= 0) return null;
      return ((dTotal - dIdle) / dTotal * 100).clamp(0.0, 100.0).toDouble();
    }

    final sample = await _readProcStat();
    if (sample != null) {
      final prev = _prevCpuSample;
      if (prev != null) {
        _prevCpuSample = sample;
        final percent = computePercent(prev, sample);
        if (percent != null) {
          return CpuMetrics(percent: percent, coreCount: coreCount);
        }
        // Fall through to the next attempt when the delta is unusable.
      } else {
        // First read: take a second sample ~350ms later so the percentage is
        // a real reading instead of 0.
        await Future<void>.delayed(const Duration(milliseconds: 350));
        final second = await _readProcStat();
        _prevCpuSample = second ?? sample;
        if (second != null) {
          final percent = computePercent(sample, second);
          if (percent != null) {
            return CpuMetrics(percent: percent, coreCount: coreCount);
          }
        }
      }
    }

    // Fallback: /proc/loadavg estimate (load1 / cores), readable everywhere.
    final loadText = await _readProcFile('/proc/loadavg');
    if (loadText.isNotEmpty) {
      final load1 = double.tryParse(loadText.trim().split(RegExp(r'\s+')).first);
      if (load1 != null && load1 >= 0) {
        final cores = coreCount < 1 ? 1 : coreCount;
        return CpuMetrics(
          percent: (load1 / cores * 100).clamp(0.0, 100.0).toDouble(),
          coreCount: coreCount,
        );
      }
    }

    // Nothing readable -> null percent, shown as N/A (never a misleading 0%).
    return CpuMetrics(percent: null, coreCount: coreCount);
  }

  /// Reads the aggregate "cpu" line of /proc/stat as {total, idle} ticks;
  /// null if the file is unreadable or the line is malformed.
  Future<({int total, int idle})?> _readProcStat() async {
    final text = await _readProcFile('/proc/stat');
    if (text.isEmpty) return null;
    final line = text
        .split('\n')
        .firstWhere((l) => l.startsWith('cpu '), orElse: () => '');
    if (line.isEmpty) return null;
    final fields = line
        .split(RegExp(r'\s+'))
        .skip(1)
        .map(int.tryParse)
        .whereType<int>()
        .toList();
    if (fields.isEmpty) return null;
    final idle =
        (fields.length > 3 ? fields[3] : 0) + (fields.length > 4 ? fields[4] : 0);
    final total = fields.fold<int>(0, (sum, f) => sum + f);
    if (total <= 0) return null;
    return (total: total, idle: idle);
  }

  /// Reads a file to EOF via a stream. dart:io's readAsString() sizes its
  /// buffer from fstat's st_size, which is always 0 on procfs files
  /// (/proc/*), so it silently returns ""; stream reads go to EOF and work.
  Future<String> _readProcFile(String path) async {
    try {
      final builder = BytesBuilder(copy: false);
      await File(path).openRead().forEach(builder.add);
      return utf8.decode(builder.takeBytes(), allowMalformed: true);
    } catch (_) {
      return '';
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
