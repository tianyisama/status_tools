/// Data model for a device's metrics, mirroring `protocol/schema.json`.
///
/// Fields that cannot be read are set to `null` (never omitted) so the desktop
/// peer always sees the same shape.
library;

class CpuMetrics {
  // null when /proc is unreadable on the device (shown as N/A, never as 0%).
  final double? percent;
  final int coreCount;
  final double? temperatureC; // not available on Android without root
  // Which reader produced the value: proc | loadavg | channel | none.
  // Display-only, not part of the wire protocol.
  final String source;
  CpuMetrics({
    required this.percent,
    required this.coreCount,
    this.temperatureC,
    this.source = 'proc',
  });

  Map<String, dynamic> toJson() => {
        'percent': percent == null ? null : _round(percent!),
        'core_count': coreCount,
        'temperature_c': temperatureC,
      };
}

class GpuMetrics {
  final bool available;
  final double? percent;
  final int? memoryUsedMb;
  final int? memoryTotalMb;
  final double? temperatureC;

  GpuMetrics.unavailable()
      : available = false,
        percent = null,
        memoryUsedMb = null,
        memoryTotalMb = null,
        temperatureC = null;

  Map<String, dynamic> toJson() => {
        'available': available,
        'percent': percent == null ? null : _round(percent!),
        'memory_used_mb': memoryUsedMb,
        'memory_total_mb': memoryTotalMb,
        'temperature_c': temperatureC,
      };
}

class MemoryMetrics {
  final double percent;
  final int usedMb;
  final int totalMb;
  MemoryMetrics({required this.percent, required this.usedMb, required this.totalMb});

  Map<String, dynamic> toJson() => {
        'percent': _round(percent),
        'used_mb': usedMb,
        'total_mb': totalMb,
      };
}

class DiskMetrics {
  final double percent;
  final double usedGb;
  final double totalGb;
  DiskMetrics({required this.percent, required this.usedGb, required this.totalGb});

  Map<String, dynamic> toJson() => {
        'percent': _round(percent),
        'used_gb': _round(usedGb),
        'total_gb': _round(totalGb),
      };
}

class BatteryMetrics {
  final bool present;
  final double? percent;
  final bool? plugged;
  // charging | discharging | full | no_battery | unknown
  final String status;
  final double? temperatureC;

  BatteryMetrics({
    required this.present,
    required this.percent,
    required this.plugged,
    required this.status,
    this.temperatureC,
  });

  Map<String, dynamic> toJson() => {
        'present': present,
        'percent': percent == null ? null : _round(percent!),
        'plugged': plugged,
        'status': status,
        'temperature_c': temperatureC,
      };
}

class MetricsPayload {
  final CpuMetrics cpu;
  final GpuMetrics gpu;
  final MemoryMetrics memory;
  final DiskMetrics disk;
  final BatteryMetrics battery;

  MetricsPayload({
    required this.cpu,
    required this.gpu,
    required this.memory,
    required this.disk,
    required this.battery,
  });

  /// The `data` field of a `metrics` message (see protocol/SPEC.md).
  Map<String, dynamic> toDataJson() => {
        'cpu': cpu.toJson(),
        'gpu': gpu.toJson(),
        'memory': memory.toJson(),
        'disk': disk.toJson(),
        'battery': battery.toJson(),
      };
}

double _round(double v) => (v * 10).roundToDouble() / 10;
