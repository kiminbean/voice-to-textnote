// 오디오 레벨 미터 위젯
// @MX:NOTE: SPEC-APP-005 REQ-002 — 0~100% 실시간 오디오 레벨 시각화

import 'package:flutter/material.dart';

/// 녹음 중 실시간 오디오 레벨 미터 (0~100%)
class AudioLevelMeter extends StatelessWidget {
  /// 0.0 ~ 1.0 사이의 레벨 값
  final double level;

  /// 활성화 여부 (녹음 중이 아닐 때 비활성화)
  final bool isActive;

  /// 높이 (기본 8.0)
  final double height;

  const AudioLevelMeter({
    super.key,
    required this.level,
    this.isActive = true,
    this.height = 8.0,
  });

  @override
  Widget build(BuildContext context) {
    // 레벨 값을 0~1 사이로 클램핑
    final clampedLevel = level.clamp(0.0, 1.0);
    final displayLevel = isActive ? clampedLevel : 0.0;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // 레벨 바
        ClipRRect(
          borderRadius: BorderRadius.circular(height / 2),
          child: SizedBox(
            width: 200,
            height: height,
            child: Stack(
              children: [
                // 배경
                Container(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                ),
                // 레벨 표시
                AnimatedFractionallySizedBox(
                  duration: const Duration(milliseconds: 50),
                  alignment: Alignment.centerLeft,
                  widthFactor: displayLevel,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: _getLevelColors(displayLevel),
                      ),
                      borderRadius: BorderRadius.circular(height / 2),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 4),
        // 퍼센트 텍스트
        Text(
          '${(displayLevel * 100).round()}%',
          style: TextStyle(
            fontSize: 12,
            color: isActive
                ? Theme.of(context).colorScheme.onSurfaceVariant
                : Theme.of(context).disabledColor,
          ),
        ),
      ],
    );
  }

  /// 레벨에 따른 색상 그라데이션
  List<Color> _getLevelColors(double level) {
    if (level < 0.3) {
      return [Colors.green.shade300, Colors.green.shade500];
    } else if (level < 0.7) {
      return [Colors.green.shade500, Colors.yellow.shade600];
    } else {
      return [Colors.yellow.shade600, Colors.red.shade400];
    }
  }
}
