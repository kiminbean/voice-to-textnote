// 처리 중 화면 - 파이프라인 진행 상황 표시
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/providers/pipeline_provider.dart';
import 'package:voice_to_textnote/widgets/pipeline_progress.dart';

class ProcessingScreen extends ConsumerWidget {
  final String meetingId;

  const ProcessingScreen({super.key, required this.meetingId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pipelineState = ref.watch(pipelineProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('처리 중'),
        automaticallyImplyLeading: false, // 뒤로가기 비활성화
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 처리 상태 텍스트
            Text(
              _getStepText(pipelineState.currentStep),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 32),
            // 파이프라인 진행 표시
            PipelineProgress(pipelineState: pipelineState),
            const SizedBox(height: 24),
            // 진행률 퍼센트 표시
            Text(
              '${(pipelineState.progress * 100).toInt()}%',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            // 오류 메시지 표시
            if (pipelineState.errorMessage != null) ...[
              const SizedBox(height: 16),
              Text(
                '오류: ${pipelineState.errorMessage}',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.red),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // 처리 단계에 따른 텍스트 반환
  String _getStepText(PipelineStep step) {
    return switch (step) {
      PipelineStep.idle => '처리 시작 대기 중',
      PipelineStep.uploading => '오디오 파일 업로드 중...',
      PipelineStep.transcribing => '음성 인식(STT) 처리 중...',
      PipelineStep.diarizing => '화자 분리 처리 중...',
      PipelineStep.generatingMinutes => '회의록 생성 중...',
      PipelineStep.summarizing => 'AI 요약 생성 중...',
      PipelineStep.completed => '처리 완료!',
      PipelineStep.failed => '처리 실패',
    };
  }
}
