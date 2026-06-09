// 파이프라인 처리 상태 모델
// @MX:NOTE: SPEC-APP-005 — 단계별 결과/타이밍/에러 추적 추가 (REQ-009~012, REQ-021)

// 파이프라인 처리 단계 열거형
enum PipelineStep {
  idle, // 대기 중
  uploading, // 업로드 중
  transcribing, // 음성 인식 중 (STT)
  diarizing, // 화자 분리 중
  generatingMinutes, // 회의록 생성 중
  summarizing, // AI 요약 중
  completed, // 완료
  failed, // 실패
}

/// 단계별 결과 데이터
class StageResult {
  final PipelineStep step;
  final dynamic data;
  final DateTime completedAt;

  const StageResult({
    required this.step,
    required this.data,
    required this.completedAt,
  });
}

/// 단계별 타이밍 데이터 (REQ-021)
class StageTiming {
  final PipelineStep step;
  final Duration duration;
  final DateTime startedAt;
  final DateTime completedAt;

  const StageTiming({
    required this.step,
    required this.duration,
    required this.startedAt,
    required this.completedAt,
  });
}

// 파이프라인 처리 상태 모델
class PipelineState {
  // 현재 처리 단계
  final PipelineStep currentStep;

  // 전체 진행률 (0.0 ~ 1.0)
  final double progress;

  // 오류 메시지 (실패 시)
  final String? errorMessage;

  // 현재 처리 중인 태스크 ID
  final String? currentTaskId;

  // ResultScreen에서 결과 조회에 사용할 task ID들
  final String? minutesTaskId;
  final String? summaryTaskId;

  // SPEC-APP-005: 단계별 결과 (REQ-009, REQ-010)
  final Map<PipelineStep, StageResult> stageResults;

  // SPEC-APP-005: 단계별 타이밍 (REQ-021)
  final Map<PipelineStep, StageTiming> stageTimings;

  // SPEC-APP-005: 단계별 에러 (REQ-011, REQ-012)
  final Map<PipelineStep, String> stageErrors;

  // SPEC-APP-005: 실패한 단계 (재시도 대상)
  final PipelineStep? failedStep;

  const PipelineState({
    required this.currentStep,
    required this.progress,
    this.errorMessage,
    this.currentTaskId,
    this.minutesTaskId,
    this.summaryTaskId,
    this.stageResults = const {},
    this.stageTimings = const {},
    this.stageErrors = const {},
    this.failedStep,
  });

  // 특정 필드만 변경한 복사본 반환
  PipelineState copyWith({
    PipelineStep? currentStep,
    double? progress,
    String? errorMessage,
    bool clearErrorMessage = false,
    String? currentTaskId,
    bool clearCurrentTaskId = false,
    String? minutesTaskId,
    String? summaryTaskId,
    Map<PipelineStep, StageResult>? stageResults,
    Map<PipelineStep, StageTiming>? stageTimings,
    Map<PipelineStep, String>? stageErrors,
    PipelineStep? failedStep,
    bool clearFailedStep = false,
  }) {
    return PipelineState(
      currentStep: currentStep ?? this.currentStep,
      progress: progress ?? this.progress,
      errorMessage: clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
      currentTaskId: clearCurrentTaskId ? null : (currentTaskId ?? this.currentTaskId),
      minutesTaskId: minutesTaskId ?? this.minutesTaskId,
      summaryTaskId: summaryTaskId ?? this.summaryTaskId,
      stageResults: stageResults ?? this.stageResults,
      stageTimings: stageTimings ?? this.stageTimings,
      stageErrors: stageErrors ?? this.stageErrors,
      failedStep: clearFailedStep ? null : (failedStep ?? this.failedStep),
    );
  }

  // 초기 상태 팩토리
  factory PipelineState.initial() {
    return const PipelineState(
      currentStep: PipelineStep.idle,
      progress: 0.0,
    );
  }

  /// 특정 단계의 결과가 있는지 확인 (REQ-010)
  bool hasStageResult(PipelineStep step) => stageResults.containsKey(step);

  /// 특정 단계가 실패했는지 확인 (REQ-012)
  bool isStepFailed(PipelineStep step) => stageErrors.containsKey(step);

  /// 재시도 가능한 실패 단계가 있는지 확인 (REQ-011)
  bool get canRetry => failedStep != null;

  /// 특정 단계의 소요 시간 (REQ-021)
  Duration? getStageDuration(PipelineStep step) => stageTimings[step]?.duration;
}
