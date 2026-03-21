// 파이프라인 처리 상태 관리 프로바이더
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/services/diarization_api.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';
import 'package:voice_to_textnote/services/transcription_api.dart';

// 파이프라인 Notifier
class PipelineNotifier extends Notifier<PipelineState> {
  // 폴링 취소 플래그 - 화면 이탈 또는 사용자 취소 시 true로 설정
  bool _cancelled = false;

  // 폴링 최대 횟수 (2초 간격 × 300 = 10분)
  static const int _maxPollingAttempts = 300;

  @override
  PipelineState build() {
    return PipelineState.initial();
  }

  // 파이프라인 취소 - 화면 종료 시 또는 명시적 취소 시 호출
  Future<void> cancelPipeline() async {
    _cancelled = true;
  }

  // 파이프라인 전체 처리 시작
  // 업로드 -> STT 폴링 -> 화자 분리 -> 화자 분리 폴링 -> 회의록 생성 -> 회의록 폴링 -> 요약 -> 요약 폴링 -> 완료
  Future<void> startPipeline(String audioFilePath) async {
    // 새 파이프라인 시작 시 취소 플래그 초기화
    _cancelled = false;
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
      // ResultScreen 조회용으로 minutesTaskId 저장
      state = state.copyWith(minutesTaskId: minTaskId);

      // 6단계: 회의록 폴링
      await _pollUntilCompleted(() => minApi.getStatus(minTaskId));

      // 7단계: 요약 생성
      state = state.copyWith(
        currentStep: PipelineStep.summarizing,
        progress: 0.8,
      );
      final sumResult = await sumApi.create(minTaskId);
      final sumTaskId = sumResult['task_id'] as String;
      // ResultScreen 조회용으로 summaryTaskId 저장
      state = state.copyWith(summaryTaskId: sumTaskId);

      // 8단계: 요약 폴링
      await _pollUntilCompleted(() => sumApi.getStatus(sumTaskId));

      // 완료 - currentTaskId를 명시적으로 null 클리어
      state = state.copyWith(
        currentStep: PipelineStep.completed,
        progress: 1.0,
        clearCurrentTaskId: true,
      );
    } catch (e) {
      // 취소된 경우 상태 업데이트 생략
      if (_cancelled) return;

      // DioException을 사용자 친화적 한국어 메시지로 변환
      final String userMessage;
      if (e is DioException) {
        userMessage = switch (e.type) {
          DioExceptionType.connectionTimeout => '서버 연결 시간이 초과되었습니다',
          DioExceptionType.receiveTimeout => '서버 응답 시간이 초과되었습니다',
          DioExceptionType.sendTimeout => '요청 전송 시간이 초과되었습니다',
          DioExceptionType.connectionError => '서버에 연결할 수 없습니다',
          DioExceptionType.badResponse =>
            '서버 처리 중 오류가 발생했습니다 (${e.response?.statusCode})',
          _ => '네트워크 오류가 발생했습니다',
        };
      } else {
        userMessage = '처리 중 오류가 발생했습니다';
      }

      state = state.copyWith(
        currentStep: PipelineStep.failed,
        errorMessage: userMessage,
        clearCurrentTaskId: true,
      );
    }
  }

  // 태스크가 completed 될 때까지 폴링
  // 취소 플래그(_cancelled) 또는 최대 횟수(10분) 초과 시 종료
  Future<void> _pollUntilCompleted(
    Future<Map<String, dynamic>> Function() getStatus,
  ) async {
    int attempts = 0;
    while (!_cancelled && attempts < _maxPollingAttempts) {
      attempts++;
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

    if (_cancelled) {
      throw Exception('파이프라인이 취소되었습니다');
    }
    if (attempts >= _maxPollingAttempts) {
      throw Exception('처리 시간이 초과되었습니다 (10분)');
    }
  }

  // 파이프라인 상태 초기화
  void reset() {
    _cancelled = false;
    state = PipelineState.initial();
  }
}

// 파이프라인 프로바이더
final pipelineProvider = NotifierProvider<PipelineNotifier, PipelineState>(
  PipelineNotifier.new,
);
