// 부분 결과 표시 패널 위젯
// @MX:NOTE: SPEC-APP-005 REQ-009,010 — 완료된 단계의 결과를 즉시 표시

import 'package:flutter/material.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';

/// 완료된 파이프라인 단계의 결과를 즉시 표시하는 패널 (REQ-009, REQ-010)
class PartialResultPanel extends StatelessWidget {
  final PipelineState pipelineState;
  final VoidCallback? onRetryFailed;

  const PartialResultPanel({
    super.key,
    required this.pipelineState,
    this.onRetryFailed,
  });

  @override
  Widget build(BuildContext context) {
    final completedSteps = _getCompletedSteps();
    final failedSteps = _getFailedSteps();

    if (completedSteps.isEmpty && failedSteps.isEmpty) {
      return const SizedBox.shrink();
    }

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '단계별 결과',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const Divider(height: 16),
            // 완료된 단계 표시
            ...completedSteps.map((step) => _buildStepTile(
                  context,
                  step: step,
                  isCompleted: true,
                )),
            // 실패한 단계 표시 + 재시도 버튼 (REQ-011, REQ-012)
            ...failedSteps.map((step) => _buildStepTile(
                  context,
                  step: step,
                  isCompleted: false,
                )),
          ],
        ),
      ),
    );
  }

  Widget _buildStepTile(
    BuildContext context, {
    required PipelineStep step,
    required bool isCompleted,
  }) {
    final stepLabel = _getStepLabel(step);
    final timing = pipelineState.getStageDuration(step);
    final timingText = timing != null
        ? '${timing.inSeconds}초'
        : null;

    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        isCompleted ? Icons.check_circle : Icons.error,
        color: isCompleted ? Colors.green : Colors.red,
        size: 20,
      ),
      title: Text(
        stepLabel,
        style: TextStyle(
          fontSize: 14,
          color: isCompleted ? null : Colors.red,
        ),
      ),
      subtitle: timingText != null
          ? Text(
              '소요 시간: $timingText',
              style: const TextStyle(fontSize: 11),
            )
          : null,
      trailing: isCompleted
          ? null
          : TextButton.icon(
              onPressed: onRetryFailed,
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('재시도'),
              style: TextButton.styleFrom(
                foregroundColor: Colors.red,
                padding: const EdgeInsets.symmetric(horizontal: 8),
              ),
            ),
    );
  }

  /// 완료된 단계 목록
  List<PipelineStep> _getCompletedSteps() {
    return PipelineStep.values
        .where((s) => pipelineState.hasStageResult(s))
        .toList();
  }

  /// 실패한 단계 목록
  List<PipelineStep> _getFailedSteps() {
    return PipelineStep.values
        .where((s) => pipelineState.isStepFailed(s))
        .toList();
  }

  String _getStepLabel(PipelineStep step) {
    return switch (step) {
      PipelineStep.idle => '대기',
      PipelineStep.uploading => '업로드',
      PipelineStep.transcribing => '음성 인식 (STT)',
      PipelineStep.diarizing => '화자 분리',
      PipelineStep.generatingMinutes => '회의록 생성',
      PipelineStep.summarizing => 'AI 요약',
      PipelineStep.completed => '완료',
      PipelineStep.failed => '실패',
    };
  }
}
