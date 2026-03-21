// 오류 다이얼로그 위젯 - Material 3 스타일
import 'package:flutter/material.dart';

class ErrorDialog extends StatelessWidget {
  // 사용자에게 표시할 한국어 오류 메시지
  final String message;

  // 재시도 콜백 (null이면 버튼 미표시)
  final VoidCallback? onRetry;

  // 홈으로 이동 콜백 (null이면 버튼 미표시)
  final VoidCallback? onGoHome;

  const ErrorDialog({
    super.key,
    required this.message,
    this.onRetry,
    this.onGoHome,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return AlertDialog(
      icon: Icon(
        Icons.error_outline,
        color: colorScheme.error,
        size: 32,
      ),
      title: const Text('오류'),
      content: Text(
        message,
        style: Theme.of(context).textTheme.bodyMedium,
      ),
      actions: [
        // 홈으로 버튼 (제공된 경우)
        if (onGoHome != null)
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              onGoHome!();
            },
            child: const Text('홈으로'),
          ),
        // 재시도 버튼 (제공된 경우)
        if (onRetry != null)
          FilledButton(
            onPressed: () {
              Navigator.of(context).pop();
              onRetry!();
            },
            child: const Text('재시도'),
          ),
        // 버튼이 없을 때 기본 닫기 버튼
        if (onRetry == null && onGoHome == null)
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('확인'),
          ),
      ],
    );
  }
}
