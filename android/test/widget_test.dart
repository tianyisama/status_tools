// Unit tests for the metrics model / protocol shape. These do not require the
// Android platform channels, so they run in plain `flutter test` (including CI).

import 'package:flutter_test/flutter_test.dart';

import 'package:status_tools/models/metrics.dart';

void main() {
  test('MetricsPayload.toDataJson matches the protocol schema shape', () {
    final payload = MetricsPayload(
      cpu: CpuMetrics(percent: 34.25, coreCount: 8),
      gpu: GpuMetrics.unavailable(),
      memory: MemoryMetrics(percent: 61.5, usedMb: 4820, totalMb: 7864),
      disk: DiskMetrics(percent: 72.34, usedGb: 92.1, totalGb: 127.4),
      battery: BatteryMetrics(present: true, percent: 28.0, plugged: false, status: 'discharging'),
    );

    final data = payload.toDataJson();

    // Top-level sections present.
    expect(data.keys, containsAll(['cpu', 'gpu', 'memory', 'disk', 'battery']));

    // CPU
    expect(data['cpu']['percent'], 34.3); // rounded to 1 decimal
    expect(data['cpu']['core_count'], 8);

    // GPU unavailable -> nulls, not omitted.
    final gpu = data['gpu'];
    expect(gpu['available'], false);
    expect(gpu.containsKey('percent'), true);
    expect(gpu['percent'], isNull);
    expect(gpu['memory_used_mb'], isNull);

    // Memory / disk rounding.
    expect(data['memory']['percent'], 61.5);
    expect(data['disk']['percent'], 72.3);

    // Battery.
    final battery = data['battery'];
    expect(battery['present'], true);
    expect(battery['percent'], 28.0);
    expect(battery['plugged'], false);
    expect(battery['status'], 'discharging');
  });

  test('No-battery payload reports no_battery status', () {
    final battery = BatteryMetrics(present: false, percent: null, plugged: null, status: 'no_battery');
    final json = battery.toJson();
    expect(json['present'], false);
    expect(json['percent'], isNull);
    expect(json['status'], 'no_battery');
  });
}
