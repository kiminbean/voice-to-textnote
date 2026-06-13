import 'package:flutter/material.dart';

/// @MX:SPEC:REQ-MOBILE-009-05
///
/// 오프라인 결과가 온라인 백엔드 재처리 결과로 개선되었음을 표시합니다.
class ImprovedResultBadge extends StatelessWidget {
  const ImprovedResultBadge({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      label: '개선된 결과',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: theme.colorScheme.primaryContainer,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.verified_outlined,
              size: 16,
              color: theme.colorScheme.onPrimaryContainer,
            ),
            const SizedBox(width: 6),
            Text(
              '개선된 결과',
              style: theme.textTheme.labelMedium?.copyWith(
                color: theme.colorScheme.onPrimaryContainer,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
