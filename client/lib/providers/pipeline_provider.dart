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

  // 폴링 최대 횟수 (2초 간격 × 150 = 5분)
  static const int _maxPollingAttempts = 150;

  // pending 상태 장기 체류 감지 임계값 (연속 90회 = 3분)
  // STT 모델 최초 로드 + 큐 대기 시간을 고려한 값
  static const int _stalePendingThreshold = 90;

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
  // templateId: 요약 생성 시 사용할 양식 ID (null = 기본 양식)
  Future<void> startPipeline(String audioFilePath, {String? templateId}) async {
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

      // 7단계: 요약 생성 (templateId가 있으면 양식 기반 요약)
      state = state.copyWith(
        currentStep: PipelineStep.summarizing,
        progress: 0.8,
      );
      final sumResult = await sumApi.create(minTaskId, templateId: templateId);
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
        userMessage = e.toString().replaceFirst('Exception: ', '');
      }

      state = state.copyWith(
        currentStep: PipelineStep.failed,
        errorMessage: userMessage,
        clearCurrentTaskId: true,
      );
    }
  }

  // 태스크가 completed 될 때까지 폴링
  // 취소 플래그(_cancelled) 또는 최대 횟수(3분) 초과 시 종료
  Future<void> _pollUntilCompleted(
    Future<Map<String, dynamic>> Function() getStatus,
  ) async {
    int attempts = 0;
    int pendingCount = 0; // pending 상태 연속 횟수

    while (!_cancelled && attempts < _maxPollingAttempts) {
      attempts++;

      try {
        final status = await getStatus();
        final statusStr = status['status'] as String?;

        if (statusStr == null) {
          throw Exception('서버 응답에 status 필드가 없습니다');
        }

        if (statusStr == 'completed') {
          return;
        } else if (statusStr == 'failed') {
          final errorMsg =
              status['error_message'] ?? status['error'] ?? '알 수 없는 오류';
          throw Exception('태스크 처리 실패: $errorMsg');
        } else if (statusStr == 'pending') {
          pendingCount++;
          if (pendingCount >= _stalePendingThreshold) {
            throw Exception(
              '처리 시간이 초과되었습니다. '
              '서버 상태를 확인하세요.',
            );
          }
        } else {
          // processing 등 진행 중 상태 → pending 카운터 리셋
          pendingCount = 0;

          // 서버에서 보고한 진행률을 UI에 반영
          final serverProgress = status['progress'] as num?;
          if (serverProgress != null && serverProgress > 0) {
            final currentBase = state.progress;
            // 현재 단계 내에서 서버 진행률을 보간
            const stepRange = 0.2; // 각 단계가 차지하는 전체 진행률 비율
            final adjustedProgress =
                currentBase + (serverProgress.toDouble() * stepRange);
            if (adjustedProgress > state.progress) {
              state = state.copyWith(progress: adjustedProgress.clamp(0.0, 0.99));
            }
          }
        }
      } on DioException {
        // 네트워크 오류는 상위로 전파하여 사용자 친화적 메시지 표시
        rethrow;
      }

      // 폴링 간격 대기
      await Future.delayed(AppConfig.pollingInterval);
    }

    if (_cancelled) {
      throw Exception('파이프라인이 취소되었습니다');
    }
    if (attempts >= _maxPollingAttempts) {
      throw Exception('처리 시간이 초과되었습니다 (3분)');
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
