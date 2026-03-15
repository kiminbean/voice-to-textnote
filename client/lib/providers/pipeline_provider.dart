// 파이프라인 처리 상태 관리 프로바이더
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/services/diarization_api.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';
import 'package:voice_to_textnote/services/transcription_api.dart';

// 파이프라인 Notifier
class PipelineNotifier extends Notifier<PipelineState> {
  @override
  PipelineState build() {
    return PipelineState.initial();
  }

  // 파이프라인 전체 처리 시작
  // 업로드 -> STT 폴링 -> 화자 분리 -> 화자 분리 폴링 -> 회의록 생성 -> 회의록 폴링 -> 요약 -> 요약 폴링 -> 완료
  Future<void> startPipeline(String audioFilePath) async {
    final sttApi = ref.read(transcriptionApiProvider);
    final diaApi = ref.read(diarizationApiProvider);
    final minApi = ref.read(minutesApiProvider);
    final sumApi = ref.read(summaryApiProvider);

    try {
      // 1단계: 업로드
      state = state.copyWith(
        currentStep: PipelineStep.uploading,
        progress: 0.0,
      );
      final uploadResult = await sttApi.upload(audioFilePath);
      final sttTaskId = uploadResult['task_id'] as String;

      // 2단계: STT 폴링
      state = state.copyWith(
        currentStep: PipelineStep.transcribing,
        progress: 0.2,
        currentTaskId: sttTaskId,
      );
      await _pollUntilCompleted(() => sttApi.getStatus(sttTaskId));

      // 3단계: 화자 분리 생성
      state = state.copyWith(
        currentStep: PipelineStep.diarizing,
        progress: 0.4,
      );
      final diaResult = await diaApi.create(sttTaskId);
      final diaTaskId = diaResult['task_id'] as String;

      // 4단계: 화자 분리 폴링
      await _pollUntilCompleted(() => diaApi.getStatus(diaTaskId));

      // 5단계: 회의록 생성
      state = state.copyWith(
        currentStep: PipelineStep.generatingMinutes,
        progress: 0.6,
      );
      final minResult = await minApi.create(diaTaskId);
      final minTaskId = minResult['task_id'] as String;

      // 6단계: 회의록 폴링
      await _pollUntilCompleted(() => minApi.getStatus(minTaskId));

      // 7단계: 요약 생성
      state = state.copyWith(
        currentStep: PipelineStep.summarizing,
        progress: 0.8,
      );
      final sumResult = await sumApi.create(minTaskId);
      final sumTaskId = sumResult['task_id'] as String;

      // 8단계: 요약 폴링
      await _pollUntilCompleted(() => sumApi.getStatus(sumTaskId));

      // 완료
      state = state.copyWith(
        currentStep: PipelineStep.completed,
        progress: 1.0,
        currentTaskId: null,
      );
    } catch (e) {
      // 실패 처리
      state = state.copyWith(
        currentStep: PipelineStep.failed,
        errorMessage: e.toString(),
        currentTaskId: null,
      );
    }
  }

  // 태스크가 completed 될 때까지 폴링
  Future<void> _pollUntilCompleted(
    Future<Map<String, dynamic>> Function() getStatus,
  ) async {
    while (true) {
      final status = await getStatus();
      final statusStr = status['status'] as String?;

      if (statusStr == 'completed') {
        return;
      } else if (statusStr == 'failed') {
        throw Exception('태스크 처리 실패: ${status['error'] ?? '알 수 없는 오류'}');
      }

      // 폴링 간격 대기
      await Future.delayed(AppConfig.pollingInterval);
    }
  }

  // 파이프라인 상태 초기화
  void reset() {
    state = PipelineState.initial();
  }
}

// 파이프라인 프로바이더
final pipelineProvider = NotifierProvider<PipelineNotifier, PipelineState>(
  PipelineNotifier.new,
);
