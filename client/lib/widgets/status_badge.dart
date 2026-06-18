// 상태 배지 공용 위젯 — 소프트 컬러 + 알약형
// @MX:NOTE: meeting_card, result_screen, processing_screen 등에서 재사용.
import 'package:flutter/material.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';

enum BadgeTone { neutral, success, warning, danger, info, brand }

class StatusBadge extends StatelessWidget {
  final String label;
  final BadgeTone tone;
  final IconData? icon;
  final bool dot;
  final double? fontSize;

  const StatusBadge({
    super.key,
    required this.label,
    this.tone = BadgeTone.neutral,
    this.icon,
    this.dot = false,
    this.fontSize,
  });

  /// 상태 텍스트에서 톤을 자동 추론하는 헬퍼
  factory StatusBadge.auto({
    Key? key,
    required String label,
    IconData? icon,
    bool dot = false,
  }) {
    final tone = switch (label) {
      '완료' || 'completed' || 'done' || 'success' => BadgeTone.success,
      '처리 중' || 'processing' || '진행 중' || '녹음 중' || 'recording' =>
        BadgeTone.warning,
      '실패' || 'failed' || 'error' => BadgeTone.danger,
      _ => BadgeTone.neutral,
    };
    return StatusBadge(key: key, label: label, tone: tone, icon: icon, dot: dot);
  }

  (Color, Color) _colors(AppColorScheme scheme) => switch (tone) {
        BadgeTone.neutral => (scheme.textSecondary, scheme.surfaceAlt),
        BadgeTone.success => (AppColors.success, AppColors.successSoft),
        BadgeTone.warning => (AppColors.warning, AppColors.warningSoft),
        BadgeTone.danger => (AppColors.error, AppColors.errorSoft),
        BadgeTone.info => (AppColors.info, scheme.primarySoft),
        BadgeTone.brand => (scheme.primary, scheme.primarySoft),
      };

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    final (fg, bg) = _colors(scheme);
    // 다크모드에서는 소프트 배경을 더 어둡게
    final resolvedBg = scheme.isDark ? fg.withAlpha(36) : bg;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm + 2, vertical: 5),
      decoration: BoxDecoration(
        color: resolvedBg,
        borderRadius: AppRadius.brPill,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (dot) ...[
            Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(color: fg, shape: BoxShape.circle),
            ),
            const SizedBox(width: 6),
          ] else if (icon != null) ...[
            Icon(icon, size: 12, color: fg),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: TextStyle(
              color: fg,
              fontSize: fontSize ?? 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.1,
            ),
          ),
        ],
      ),
    );
  }
}
