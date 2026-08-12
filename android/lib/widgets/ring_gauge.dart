/// An animated circular gauge used for CPU / memory / battery.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

class RingGauge extends StatelessWidget {
  final double value; // 0..100
  final String label;
  final IconData icon;
  final Color? color;
  final String? caption;
  final double size;

  const RingGauge({
    super.key,
    required this.value,
    required this.label,
    required this.icon,
    this.color,
    this.caption,
    this.size = 108,
  });

  Color _color(BuildContext context) {
    if (color != null) return color!;
    if (value >= 85) return Colors.redAccent;
    if (value >= 60) return Colors.amberAccent;
    return Colors.greenAccent;
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final c = _color(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: value.clamp(0, 100).toDouble()),
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
          builder: (context, v, _) {
            return CustomPaint(
              size: Size(size, size),
              painter: _RingPainter(
                progress: v / 100,
                color: c,
                track: cs.surfaceContainerHighest,
              ),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(icon, size: 18, color: c),
                    const SizedBox(height: 2),
                    Text(
                      '${v.toInt()}%',
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: c),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
        const SizedBox(height: 8),
        Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
        if (caption != null && caption!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(caption!, style: TextStyle(fontSize: 11, color: cs.outline)),
          ),
      ],
    );
  }
}

class _RingPainter extends CustomPainter {
  final double progress;
  final Color color;
  final Color track;

  _RingPainter({required this.progress, required this.color, required this.track});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 6;
    const stroke = 9.0;

    final trackPaint = Paint()
      ..color = track.withValues(alpha: 0.55)
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, radius, trackPaint);

    if (progress > 0.001) {
      final arcPaint = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..strokeCap = StrokeCap.round;
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        -math.pi / 2,
        2 * math.pi * progress,
        false,
        arcPaint,
      );
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.progress != progress || old.color != color;
}
