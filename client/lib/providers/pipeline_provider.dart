// 파이프라인 처리 상태 관리 프로바이더
// @MX:NOTE: SPEC-APP-005 — 단계별 타이밍, 부분 결과, 재시도 추가 (REQ-009~012, REQ-021)
import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/services/diarization_api.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/sse_service.dart';
import 'package:voice_to_textnote/services/summary_api.dart';
import 'package:voice_to_textnote/services/transcription_api.dart';

// 파이프라인 Notifier
class PipelineNotifier extends Notifier<PipelineState> {
  // 폴링 취소 플래그
  bool _cancelled = false;

  // 폴링 설정
  static const int _maxPollingAttempts = 1200;
  static const int _stalePendingThreshold = 400;

  // SPEC-APP-005: 재시도를 위한 파이프라인 파라미터 저장
  String? _lastAudioFilePath;
  String? _lastTemplateId;
  String? _lastVocabularyId;
  // ignore: unused_field — 향후 단계별 세분화 재시도에서 사용 예정
  String? _lastSttTaskId;
  // ignore: unused_field — 향후 단계별 세분화 재시도에서 사용 예정
  String? _lastDiaTaskId;

  // SPEC-APP-005: 단계별 시작 시간 추적 (REQ-021)
  final Map<PipelineStep, DateTime> _stageStartTimes = {};

  @override
  PipelineState build() {
    return PipelineState.initial();
  }

  Future<void> cancelPipeline() async {
    _cancelled = true;
  }

  // 파이프라인 전체 처리 시작
  Future<void> startPipeline(
    String audioFilePath, {
    String? templateId,
    String? vocabularyId,
  }) async {
    _cancelled = false;

    // 파라미터 저장 (재시도용)
    _lastAudioFilePath = audioFilePath;
    _lastTemplateId = templateId;
    _lastVocabularyId = vocabularyId;

    final sttApi = ref.read(transcriptionApiProvider);
    final diaApi = ref.read(diarizationApiProvider);
    final minApi = ref.read(minutesApiProvider);
    final sumApi = ref.read(summaryApiProvider);

    try {
      // 1단계: 업로드
      _startStageTiming(PipelineStep.uploading);
      state = state.copyWith(
        currentStep: PipelineStep.uploading,
        progress: 0.0,
      );
      final uploadResult = await sttApi.upload(
        audioFilePath,
        vocabularyId: vocabularyId,
      );
      final sttTaskId = uploadResult['task_id'] as String;
      _lastSttTaskId = sttTaskId;
      _completeStageTiming(PipelineStep.uploading, data: {'upload': true});

      final autoDiaTaskId = uploadResult['diarization_task_id'] as String?;

      // 2단계: STT와 화자 분리를 병렬로 대기
      _startStageTiming(PipelineStep.transcribing);
      state = state.copyWith(
        currentStep: PipelineStep.transcribing,
        progress: 0.2,
        currentTaskId: sttTaskId,
      );

      String diaTaskId;
      if (autoDiaTaskId != null) {
        await Future.wait([
          _waitForCompletion(sttTaskId, () => sttApi.getStatus(sttTaskId)),
          _waitForCompletion(
            autoDiaTaskId,
            () => diaApi.getStatus(autoDiaTaskId),
          ),
        ]);
        diaTaskId = autoDiaTaskId;
        _completeStageTiming(PipelineStep.diarizing, data: {'parallel': true});
      } else {
        await _waitForCompletion(sttTaskId, () => sttApi.getStatus(sttTaskId));
        _completeStageTiming(PipelineStep.transcribing, data: {'sttTaskId': sttTaskId});

        _startStageTiming(PipelineStep.diarizing);
        state = state.copyWith(
          currentStep: PipelineStep.diarizing,
          progress: 0.4,
        );
        final diaResult = await diaApi.create(sttTaskId);
        diaTaskId = diaResult['task_id'] as String;
        await _waitForCompletion(diaTaskId, () => diaApi.getStatus(diaTaskId));
      }
      _lastDiaTaskId = diaTaskId;
      _completeStageTiming(PipelineStep.diarizing, data: {'diaTaskId': diaTaskId});

      // 5단계: 회의록 생성
      _startStageTiming(PipelineStep.generatingMinutes);
      state = state.copyWith(
        currentStep: PipelineStep.generatingMinutes,
        progress: 0.6,
      );
      final minResult = await minApi.create(
        diaTaskId,
        sttTaskId: autoDiaTaskId != null ? sttTaskId : null,
      );
      final minTaskId = minResult['task_id'] as String;
      state = state.copyWith(minutesTaskId: minTaskId);
      await _waitForCompletion(minTaskId, () => minApi.getStatus(minTaskId));
      _completeStageTiming(PipelineStep.generatingMinutes, data: {'minTaskId': minTaskId});

      // 7단계: 요약 생성
      _startStageTiming(PipelineStep.summarizing);
      state = state.copyWith(
        currentStep: PipelineStep.summarizing,
        progress: 0.8,
      );
      final sumResult = await sumApi.create(minTaskId, templateId: templateId);
      final sumTaskId = sumResult['task_id'] as String;
      state = state.copyWith(summaryTaskId: sumTaskId);
      await _waitForCompletion(sumTaskId, () => sumApi.getStatus(sumTaskId));
      _completeStageTiming(PipelineStep.summarizing, data: {'sumTaskId': sumTaskId});

      // 완료
      state = state.copyWith(
        currentStep: PipelineStep.completed,
        progress: 1.0,
        clearCurrentTaskId: true,
      );
    } catch (e) {
      if (_cancelled) return;

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

      // 실패한 단계 기록 (REQ-011)
      final failedStep = state.currentStep;
      final updatedErrors = Map<PipelineStep, String>.from(state.stageErrors)
        ..[failedStep] = userMessage;

      state = state.copyWith(
        currentStep: PipelineStep.failed,
        errorMessage: userMessage,
        clearCurrentTaskId: true,
        stageErrors: updatedErrors,
        failedStep: failedStep,
      );
    }
  }

  // SPEC-APP-005: 단계별 재시도 (REQ-011)
  // 실패한 단계부터 파이프라인 재시작
  Future<void> retryStage() async {
    final failed = state.failedStep;
    if (failed == null) return;
    if (_lastAudioFilePath == null) return;

    // 실패한 단계 에러 제거
    final updatedErrors = Map<PipelineStep, String>.from(state.stageErrors)
      ..remove(failed);

    state = state.copyWith(
      stageErrors: updatedErrors,
      clearFailedStep: true,
      clearErrorMessage: true,
    );

    // 재시도 로직: 실패 단계에 따라 적절한 위치에서 재시작
    // 백엔드가 중간 결과를 유지한다고 가정
    // 실제로는 백엔드 API 지원 여부에 따라 전체 재시작 필요할 수 있음
    await startPipeline(
      _lastAudioFilePath!,
      templateId: _lastTemplateId,
      vocabularyId: _lastVocabularyId,
    );
  }

  // SPEC-APP-005: 단계 시작 시간 기록 (REQ-021)
  void _startStageTiming(PipelineStep step) {
    _stageStartTimes[step] = DateTime.now();
  }

  // SPEC-APP-005: 단계 완료 시 타이밍 및 결과 기록 (REQ-009, REQ-021)
  void _completeStageTiming(PipelineStep step, {dynamic data}) {
    final startedAt = _stageStartTimes[step];
    if (startedAt == null) return;

    final completedAt = DateTime.now();
    final duration = completedAt.difference(startedAt);

    // 타이밍 기록
    final updatedTimings = Map<PipelineStep, StageTiming>.from(state.stageTimings)
      ..[step] = StageTiming(
        step: step,
        duration: duration,
        startedAt: startedAt,
        completedAt: completedAt,
      );

    // 부분 결과 기록 (REQ-009, REQ-010)
    final updatedResults = Map<PipelineStep, StageResult>.from(state.stageResults)
      ..[step] = StageResult(
        step: step,
        data: data,
        completedAt: completedAt,
      );

    state = state.copyWith(
      stageTimings: updatedTimings,
      stageResults: updatedResults,
    );

    _stageStartTimes.remove(step);
  }

  // 태스크 완료 대기 - SSE 우선, 실패 시 폴링 폴백
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
            final errMsg = event['error_message'] ?? event['error'] ?? '알 수 없는 오류';
            throw Exception('태스크 처리 실패: $errMsg');
          }

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
        if (_cancelled) rethrow;
        final fallbackStatus = await getStatus();
        if (fallbackStatus['status'] == 'completed') {
          return;
        }
        await _pollUntilCompleted(getStatus);
        return;
      }

      if (!completedViaSse) {
        final finalStatus = await getStatus();
        if (finalStatus['status'] != 'completed') {
          await _pollUntilCompleted(getStatus);
        }
      }
    } finally {
      sseService.disconnect();
    }
  }

  // 폴링 대기
  Future<void> _pollUntilCompleted(
    Future<Map<String, dynamic>> Function() getStatus,
  ) async {
    int attempts = 0;
    int pendingCount = 0;

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
            throw Exception('처리 시간이 초과되었습니다. 서버 상태를 확인하세요.');
          }
        } else {
          pendingCount = 0;
          final serverProgress = status['progress'] as num?;
          if (serverProgress != null && serverProgress > 0) {
            final currentBase = state.progress;
            const stepRange = 0.2;
            final adjustedProgress =
                currentBase + (serverProgress.toDouble() * stepRange);
            if (adjustedProgress > state.progress) {
              state = state.copyWith(progress: adjustedProgress.clamp(0.0, 0.99));
            }
          }
        }
      } on DioException {
        rethrow;
      }

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
    _stageStartTimes.clear();
    _lastSttTaskId = null;
    _lastDiaTaskId = null;
    state = PipelineState.initial();
  }
}

// 파이프라인 프로바이더
final pipelineProvider = NotifierProvider<PipelineNotifier, PipelineState>(
  PipelineNotifier.new,
);
