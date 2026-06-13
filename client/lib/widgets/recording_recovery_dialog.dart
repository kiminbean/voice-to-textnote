// 미완료 녹음 복구 다이얼로그 (T-010)
// 앱 재시작 시 중단된 녹음이 있으면 사용자에게 선택지 제공
import 'package:flutter/material.dart';

class RecordingRecoveryDialog extends StatelessWidget {
  final String recordingPath;
  final VoidCallback onDiscard;
  final VoidCallback onResume;

  const RecordingRecoveryDialog({
    super.key,
    required this.recordingPath,
    required this.onDiscard,
    required this.onResume,
  });

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('중단된 녹음이 있습니다'),
      content: const Text(
        '이전 녹음 세션이 정상적으로 종료되지 않았습니다.\n'
        '해당 녹음 파일을 사용하시겠습니까, 아니면 삭제하시겠습니까?',
      ),
      actions: [
        TextButton(
          onPressed: onDiscard,
          child: const Text('삭제'),
        ),
        FilledButton(
          onPressed: onResume,
          child: const Text('이어서 진행'),
        ),
      ],
    );
  }
}
