/// An animated circular gauge used for CPU / memory / battery.
///
/// The ring's centre shows only the percentage; the icon sits next to the label
/// below the ring, so the icon and the number never overlap. The centre number
/// is auto-scaled to fit inside the ring, and the whole gauge scales down on
/// narrow screens, so the text can never collide with the ring regardless of
/// the system font size or device width.
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
    this.size = 104,
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
    return FittedBox(
      fit: BoxFit.scaleDown,
      child: Column(
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
                  child: _CenterPercent(value: v.toInt(), color: c, size: size),
                ),
              );
            },
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 15, color: c),
              const SizedBox(width: 5),
              Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
            ],
          ),
          if (caption != null && caption!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Text(caption!, style: TextStyle(fontSize: 11, color: cs.outline)),
            ),
        ],
      ),
    );
  }
}

/// The "NN%" text in the ring centre, sized down when needed so it always
/// stays inside the ring. System text scaling is clamped so a large display
/// font can never push the number past the circle.
class _CenterPercent extends StatelessWidget {
  final int value;
  final Color color;
  final double size;

  const _CenterPercent({required this.value, required this.color, required this.size});

  @override
  Widget build(BuildContext context) {
    // Inner diameter of the ring: radius = size/2 - 9, stroke = 8, minus a
    // little breathing room for the round caps.
    final inner = (size - 2 * 9 - 8) * 0.9;
    return MediaQuery.withClampedTextScaling(
      maxScaleFactor: 1.15,
      child: SizedBox(
        width: inner,
        height: inner,
        child: FittedBox(
          fit: BoxFit.scaleDown,
          child: Text(
            '$value%',
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 19, color: color),
          ),
        ),
      ),
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
    final radius = size.width / 2 - 9;
    const stroke = 8.0;

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
      // Leave a small gap at 100% so the round start/end caps do not pile up
      // into a blob at the top of the ring.
      const gap = 0.06;
      final sweep = (2 * math.pi * progress - gap).clamp(0.0, 2 * math.pi - gap).toDouble();
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        -math.pi / 2,
        sweep,
        false,
        arcPaint,
      );
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.progress != progress || old.color != color;
}
