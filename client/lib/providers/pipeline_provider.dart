// 파이프라인 처리 상태 관리 프로바이더
import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'package:voice_to_textnote/models/offline_task.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/services/diarization_api.dart';
import 'package:voice_to_textnote/services/hybrid_pipeline_service.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/sse_service.dart';
import 'package:voice_to_textnote/services/summary_api.dart';
import 'package:voice_to_textnote/services/transcription_api.dart';

// 파이프라인 Notifier
class PipelineNotifier extends Notifier<PipelineState> {
  // 폴링 취소 플래그 - 화면 이탈 또는 사용자 취소 시 true로 설정
  bool _cancelled = false;

  // 폴링 최대 횟수 (3초 간격 × 1200 = 60분)
  // 30분 녹음 기준: STT ~15분 + 화자분리(CPU) ~30분 + 회의록 ~1분 + 요약 ~1분
  // 각 단계별 최대 60분까지 대기 (CPU 전용 서버에서 긴 오디오 처리 고려)
  static const int _maxPollingAttempts = 1200;

  // pending 상태 장기 체류 감지 임계값 (연속 400회 = 20분)
  // STT/화자분리 모델 최초 로드(~2분) + 큐 대기 + 긴 오디오 전처리 시간 고려
  static const int _stalePendingThreshold = 400;

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
  // vocabularyId: STT 정확도 향상용 사용자 사전 ID (null = 사전 없음)
  Future<void> startPipeline(
    String audioFilePath, {
    String? templateId,
    String? vocabularyId,
  }) async {
    // 새 파이프라인 시작 시 취소 플래그 초기화
    _cancelled = false;
    final sttApi = ref.read(transcriptionApiProvider);
    final diaApi = ref.read(diarizationApiProvider);
    final minApi = ref.read(minutesApiProvider);
    final sumApi = ref.read(summaryApiProvider);
    final hybridService = ref.read(hybridPipelineServiceProvider);
    final reprocessTask = ref.read(offlineTaskReprocessorProvider);
    hybridService.watchNetworkRecovery((task) async {
      final onlineTaskId = await reprocessTask(task);
      if (!_cancelled) {
        state = state.copyWith(
          currentTaskId: onlineTaskId,
          minutesTaskId: onlineTaskId,
          summaryTaskId: onlineTaskId,
          isOfflineResult: false,
          isImprovedResult: true,
          clearErrorMessage: true,
        );
      }
      return onlineTaskId;
    });

    try {
      if (!hybridService.isOnline) {
        await _startOfflinePipeline(audioFilePath, hybridService);
        return;
      }

      // 1단계: 업로드
      state = state.copyWith(
        currentStep: PipelineStep.uploading,
        progress: 0.0,
      );
      final uploadResult = await sttApi.upload(
        audioFilePath,
        vocabularyId: vocabularyId,
      );
      final sttTaskId = uploadResult['task_id'] as String;

      // 서버 응답에서 자동 시작된 화자 분리 task_id 추출 (병렬 모드)
      // 구버전 서버는 이 필드가 없으므로 폴백으로 별도 POST /diarizations 사용
      final autoDiaTaskId = uploadResult['diarization_task_id'] as String?;

      // 2단계: STT와 화자 분리를 병렬로 대기 (SSE)
      // 서버에서 STT 등록 직후 DIA도 함께 시작했으므로 둘은 동시에 진행 중이다.
      state = state.copyWith(
        currentStep: PipelineStep.transcribing,
        progress: 0.2,
        currentTaskId: sttTaskId,
      );

      String diaTaskId;
      if (autoDiaTaskId != null) {
        // 병렬 모드: 두 task를 동시에 대기. Future.wait로 동시 SSE listen.
        await Future.wait([
          _waitForCompletion(sttTaskId, () => sttApi.getStatus(sttTaskId)),
          _waitForCompletion(
            autoDiaTaskId,
            () => diaApi.getStatus(autoDiaTaskId),
          ),
        ]);
        diaTaskId = autoDiaTaskId;
      } else {
        // 레거시 모드: STT 완료 대기 → DIA POST → DIA 대기 (직렬)
        await _waitForCompletion(sttTaskId, () => sttApi.getStatus(sttTaskId));
        state = state.copyWith(
          currentStep: PipelineStep.diarizing,
          progress: 0.4,
        );
        final diaResult = await diaApi.create(sttTaskId);
        diaTaskId = diaResult['task_id'] as String;
        await _waitForCompletion(diaTaskId, () => diaApi.getStatus(diaTaskId));
      }

      // 5단계: 회의록 생성 (병렬 모드면 sttTaskId도 전달해 매칭 수행)
      state = state.copyWith(
        currentStep: PipelineStep.generatingMinutes,
        progress: 0.6,
      );
      final minResult = await minApi.create(
        diaTaskId,
        sttTaskId: autoDiaTaskId != null ? sttTaskId : null,
      );
      final minTaskId = minResult['task_id'] as String;
      // ResultScreen 조회용으로 minutesTaskId 저장
      state = state.copyWith(minutesTaskId: minTaskId);

      // 6단계: 회의록 완료 대기 (SSE 우선)
      await _waitForCompletion(minTaskId, () => minApi.getStatus(minTaskId));

      // 7단계: 요약 생성 (templateId가 있으면 양식 기반 요약)
      state = state.copyWith(
        currentStep: PipelineStep.summarizing,
        progress: 0.8,
      );
      final sumResult = await sumApi.create(minTaskId, templateId: templateId);
      final sumTaskId = sumResult['task_id'] as String;
      // ResultScreen 조회용으로 summaryTaskId 저장
      state = state.copyWith(summaryTaskId: sumTaskId);

      // 8단계: 요약 완료 대기 (SSE 우선)
      await _waitForCompletion(sumTaskId, () => sumApi.getStatus(sumTaskId));

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

  Future<void> _startOfflinePipeline(
    String audioFilePath,
    HybridPipelineService hybridService,
  ) async {
    state = state.copyWith(
      currentStep: PipelineStep.transcribing,
      progress: 0.2,
      isOfflineResult: true,
      isImprovedResult: false,
      clearErrorMessage: true,
    );

    final result = await hybridService.processOffline(audioFilePath);

    state = state.copyWith(
      currentStep: PipelineStep.completed,
      progress: 1.0,
      currentTaskId: result.task.id,
      minutesTaskId: result.task.id,
      summaryTaskId: result.task.id,
      isOfflineResult: true,
      isImprovedResult: false,
    );
  }

  Future<void> retryOfflineReprocess(String taskId) async {
    final hybridService = ref.read(hybridPipelineServiceProvider);
    final reprocessTask = ref.read(offlineTaskReprocessorProvider);
    final task = await hybridService.retryTask(taskId, reprocessTask);
    if (task == null) return;

    if (task.status == OfflineTaskStatus.completed) {
      state = state.copyWith(
        currentStep: PipelineStep.completed,
        currentTaskId: task.onlineTranscriptionTaskId,
        minutesTaskId: task.onlineTranscriptionTaskId,
        summaryTaskId: task.onlineTranscriptionTaskId,
        isOfflineResult: false,
        isImprovedResult: true,
        clearErrorMessage: true,
      );
    } else if (task.status == OfflineTaskStatus.failed) {
      state = state.copyWith(
        currentStep: PipelineStep.completed,
        errorMessage: task.errorMessage,
        isOfflineResult: true,
        isImprovedResult: false,
      );
    }
  }

  // 태스크 완료 대기 - SSE 우선, 실패 시 폴링 폴백
  //
  // 서버 SSE 엔드포인트(GET /api/v1/tasks/{task_id}/stream)를 통해 실시간으로
  // 상태 변화를 수신한다. 네트워크/서버 SSE 미가용 시 기존 3초 폴링으로 자동 폴백.
  //
  // - completed 이벤트 수신 → 즉시 반환 (폴링 대비 평균 1.5초 절약/단계)
  // - failed 이벤트 수신 → 예외 전파
  // - status_update 이벤트 → progress 갱신
  // - 스트림 오류 → 폴링 폴백
  Future<void> _waitForCompletion(
    String taskId,
    Future<Map<String, dynamic>> Function() getStatus,
  ) async {
    final sseService = SseService(baseUrl: AppConfig.apiBaseUrl);

    try {
      bool completedViaSse = false;
      try {
        await for (final event in sseService.connect(taskId)) {
          if (_cancelled) {
            throw Exception('파이프라인이 취소되었습니다');
          }

          final eventStatus = event['status'] as String?;
          if (eventStatus == 'completed') {
            completedViaSse = true;
            return;
          }
          if (eventStatus == 'failed') {
            final errMsg =
                event['error_message'] ?? event['error'] ?? '알 수 없는 오류';
            throw Exception('태스크 처리 실패: $errMsg');
          }

          // 서버에서 보고한 진행률을 UI에 반영 (폴링 경로와 동일한 보간 로직)
          final serverProgress = event['progress'] as num?;
          if (serverProgress != null && serverProgress > 0) {
            final currentBase = state.progress;
            const stepRange = 0.2;
            final adjustedProgress =
                currentBase + (serverProgress.toDouble() * stepRange);
            if (adjustedProgress > state.progress) {
              state = state.copyWith(
                progress: adjustedProgress.clamp(0.0, 0.99),
              );
            }
          }
        }
      } on Exception {
        // 사용자 취소나 명시적 failure는 그대로 위로 전파
        if (_cancelled) rethrow;
        // 그 외 SSE 통신 실패(네트워크/서버 미지원)는 폴링 폴백
        // 호출 직후 한 번 상태를 확인하고, 완료 아니면 기존 폴링으로 전환
        final fallbackStatus = await getStatus();
        if (fallbackStatus['status'] == 'completed') {
          return;
        }
        await _pollUntilCompleted(getStatus);
        return;
      }

      // SSE 스트림이 자연 종료됐지만 completed 이벤트가 없었던 경우 (드뭄)
      if (!completedViaSse) {
        final finalStatus = await getStatus();
        if (finalStatus['status'] != 'completed') {
          // 안전망: 폴링으로 마무리 확인
          await _pollUntilCompleted(getStatus);
        }
      }
    } finally {
      sseService.disconnect();
    }
  }

  // 태스크가 completed 될 때까지 폴링 (SSE 폴백 경로)
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
              state =
                  state.copyWith(progress: adjustedProgress.clamp(0.0, 0.99));
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
      throw Exception('처리 시간이 초과되었습니다 (60분)');
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
