import 'package:flutter/material.dart';

/// @MX:SPEC:REQ-MOBILE-008-05
///
/// 오프라인 STT 결과임을 표시하는 배지입니다.
class OfflineResultBadge extends StatelessWidget {
  final VoidCallback? onRetry;

  const OfflineResultBadge({
    super.key,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      label: '오프라인 처리됨',
      button: onRetry != null,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: theme.colorScheme.tertiaryContainer,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.cloud_off_outlined,
              size: 16,
              color: theme.colorScheme.onTertiaryContainer,
            ),
            const SizedBox(width: 6),
            Text(
              '오프라인 처리됨',
              style: theme.textTheme.labelMedium?.copyWith(
                color: theme.colorScheme.onTertiaryContainer,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (onRetry != null) ...[
              const SizedBox(width: 4),
              IconButton(
                tooltip: '온라인 재처리',
                visualDensity: VisualDensity.compact,
                constraints: const BoxConstraints.tightFor(
                  width: 28,
                  height: 28,
                ),
                padding: EdgeInsets.zero,
                icon: Icon(
                  Icons.refresh,
                  size: 16,
                  color: theme.colorScheme.onTertiaryContainer,
                ),
                onPressed: onRetry,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
