/// A single metric row: icon, label, value, and a thin progress bar.
library;

import 'package:flutter/material.dart';

class MetricCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final String? detail;
  final double? percent; // null hides the bar (e.g. GPU N/A, AC power)
  final Color? color;

  const MetricCard({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    this.detail,
    this.percent,
    this.color,
  });

  Color _barColor(BuildContext context) {
    if (color != null) return color!;
    final p = percent ?? 0;
    if (p >= 85) return Colors.redAccent;
    if (p >= 60) return Colors.orangeAccent;
    return Colors.greenAccent;
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest.withValues(alpha: 0.35),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 20, color: cs.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
              ),
              if (detail != null && detail!.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Text(detail!, style: TextStyle(fontSize: 11, color: cs.outline)),
                ),
              Text(value, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
            ],
          ),
          if (percent != null) ...[
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: (percent! / 100).clamp(0.0, 1.0),
                minHeight: 6,
                backgroundColor: cs.surfaceContainerHighest,
                valueColor: AlwaysStoppedAnimation<Color>(_barColor(context)),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
