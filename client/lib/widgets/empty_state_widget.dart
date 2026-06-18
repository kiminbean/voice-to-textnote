// 빈 상태 위젯 — 데이터가 없을 때 표시. 모던 미니멀 (큰 소프트 아이콘 + 계층)
import 'package:flutter/material.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';

class EmptyStateWidget extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  const EmptyStateWidget({
    super.key,
    this.icon = Icons.inbox_outlined,
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 소프트 아이콘 컨테이너
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: scheme.surfaceAlt,
                borderRadius: AppRadius.brLg,
              ),
              child: Icon(icon, size: 32, color: scheme.textTertiary),
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              title,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: scheme.textPrimary,
                    fontWeight: FontWeight.w600,
                  ),
            ),
            if (subtitle != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                subtitle!,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: scheme.textTertiary,
                      height: 1.5,
                    ),
              ),
            ],
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: AppSpacing.xl),
              FilledButton(
                onPressed: onAction,
                child: Text(actionLabel!),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
