// 파이프라인 처리 단계 진행 위젯 — 모던 스텝 인디케이터
import 'package:flutter/material.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';

class PipelineProgress extends StatelessWidget {
  final PipelineState pipelineState;

  const PipelineProgress({super.key, required this.pipelineState});

  static const _steps = [
    (PipelineStep.uploading, Icons.cloud_upload_outlined, '업로드'),
    (PipelineStep.transcribing, Icons.record_voice_over_outlined, 'STT'),
    (PipelineStep.diarizing, Icons.groups_outlined, '화자 분리'),
    (PipelineStep.generatingMinutes, Icons.article_outlined, '회의록'),
    (PipelineStep.summarizing, Icons.auto_awesome_outlined, 'AI 요약'),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    final isFailed = pipelineState.currentStep == PipelineStep.failed;

    return Column(
      children: [
        // 전체 진행률
        ClipRRect(
          borderRadius: AppRadius.brPill,
          child: LinearProgressIndicator(
            value: pipelineState.progress,
            minHeight: 6,
            backgroundColor: scheme.surfaceAlt,
            valueColor: AlwaysStoppedAnimation<Color>(
              isFailed ? AppColors.error : scheme.primary,
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        // 단계별 상태
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: _steps.asMap().entries.map((entry) {
            final i = entry.key;
            final (stepEnum, icon, label) = entry.value;
            final isLast = i == _steps.length - 1;
            return Expanded(
              child: _StepItem(
                icon: icon,
                label: label,
                state: _stepState(stepEnum),
                showConnector: !isLast,
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  _StepVisualState _stepState(PipelineStep step) {
    if (pipelineState.currentStep == PipelineStep.failed) return _StepVisualState.pending;
    final isCompleted = _isStepCompleted(step);
    if (isCompleted) return _StepVisualState.done;
    if (pipelineState.currentStep == step) return _StepVisualState.active;
    return _StepVisualState.pending;
  }

  bool _isStepCompleted(PipelineStep step) {
    final currentIndex = PipelineStep.values.indexOf(pipelineState.currentStep);
    final stepIndex = PipelineStep.values.indexOf(step);
    return currentIndex > stepIndex &&
        pipelineState.currentStep != PipelineStep.failed;
  }
}

enum _StepVisualState { pending, active, done }

class _StepItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final _StepVisualState state;
  final bool showConnector;

  const _StepItem({
    required this.icon,
    required this.label,
    required this.state,
    required this.showConnector,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    final (color, bg) = switch (state) {
      _StepVisualState.done => (AppColors.success, AppColors.success.withAlpha(24)),
      _StepVisualState.active => (scheme.primary, scheme.primary.withAlpha(24)),
      _StepVisualState.pending => (scheme.textTertiary, scheme.surfaceAlt),
    };
    final iconChild = state == _StepVisualState.done
        ? const Icon(Icons.check_rounded, color: Colors.white, size: 16)
        : Icon(icon, color: color, size: 18);

    return IntrinsicHeight(
      child: Row(
        children: [
          // 원형 인디케이터
          Column(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                width: state == _StepVisualState.active ? 36 : 30,
                height: state == _StepVisualState.active ? 36 : 30,
                decoration: BoxDecoration(
                  color: state == _StepVisualState.done ? AppColors.success : bg,
                  shape: BoxShape.circle,
                  border: state == _StepVisualState.done
                      ? null
                      : Border.all(color: color, width: state == _StepVisualState.active ? 1.5 : 1),
                ),
                child: Center(child: iconChild),
              ),
              const SizedBox(height: 6),
              Text(
                label,
                style: TextStyle(
                  color: state == _StepVisualState.pending ? scheme.textTertiary : scheme.textPrimary,
                  fontSize: 11,
                  fontWeight: state == _StepVisualState.active ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
            ],
          ),
          // 연결선
          if (showConnector)
            Expanded(
              child: Container(
                height: 2,
                margin: const EdgeInsets.only(top: 16, left: 2, right: 2),
                decoration: BoxDecoration(
                  color: state == _StepVisualState.done ? AppColors.success.withAlpha(80) : scheme.border,
                  borderRadius: AppRadius.brPill,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
