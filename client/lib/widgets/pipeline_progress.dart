// 파이프라인 처리 단계 진행 위젯
import 'package:flutter/material.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';

class PipelineProgress extends StatelessWidget {
  final PipelineState pipelineState;

  const PipelineProgress({
    super.key,
    required this.pipelineState,
  });

  // 5단계 파이프라인 정보
  static const _steps = [
    (PipelineStep.uploading, Icons.upload, '업로드'),
    (PipelineStep.transcribing, Icons.record_voice_over, 'STT'),
    (PipelineStep.diarizing, Icons.people, '화자 분리'),
    (PipelineStep.generatingMinutes, Icons.article, '회의록'),
    (PipelineStep.summarizing, Icons.auto_awesome, 'AI 요약'),
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // 전체 진행률 표시
        LinearProgressIndicator(
          value: pipelineState.progress,
          backgroundColor: Colors.grey[200],
          valueColor: AlwaysStoppedAnimation<Color>(
            pipelineState.currentStep == PipelineStep.failed
                ? Colors.red
                : Colors.blue,
          ),
        ),
        const SizedBox(height: 16),
        // 단계별 상태 표시
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: _steps.map((step) {
            final (stepEnum, icon, label) = step;
            return _buildStepIndicator(context, stepEnum, icon, label);
          }).toList(),
        ),
      ],
    );
  }

  // 단계 인디케이터 생성
  Widget _buildStepIndicator(
    BuildContext context,
    PipelineStep step,
    IconData icon,
    String label,
  ) {
    final isCompleted = _isStepCompleted(step);
    final isCurrent = pipelineState.currentStep == step;

    final color = isCompleted
        ? Colors.green
        : isCurrent
            ? Colors.blue
            : Colors.grey[400]!;

    return Column(
      children: [
        Icon(icon, color: color, size: isCurrent ? 32 : 24),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            color: color,
            fontSize: 12,
            fontWeight: isCurrent ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ],
    );
  }

  // 해당 단계가 완료되었는지 확인
  bool _isStepCompleted(PipelineStep step) {
    final currentIndex = PipelineStep.values.indexOf(pipelineState.currentStep);
    final stepIndex = PipelineStep.values.indexOf(step);
    return currentIndex > stepIndex &&
        pipelineState.currentStep != PipelineStep.failed;
  }
}
