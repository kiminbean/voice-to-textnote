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

  const PipelineState({
    required this.currentStep,
    required this.progress,
    this.errorMessage,
    this.currentTaskId,
    this.minutesTaskId,
    this.summaryTaskId,
  });

  // 특정 필드만 변경한 복사본 반환
  // nullable 필드를 null로 명시적 초기화하려면 clear* 플래그를 true로 설정
  PipelineState copyWith({
    PipelineStep? currentStep,
    double? progress,
    String? errorMessage,
    bool clearErrorMessage = false,
    String? currentTaskId,
    bool clearCurrentTaskId = false,
    String? minutesTaskId,
    String? summaryTaskId,
  }) {
    return PipelineState(
      currentStep: currentStep ?? this.currentStep,
      progress: progress ?? this.progress,
      errorMessage:
          clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
      currentTaskId:
          clearCurrentTaskId ? null : (currentTaskId ?? this.currentTaskId),
      minutesTaskId: minutesTaskId ?? this.minutesTaskId,
      summaryTaskId: summaryTaskId ?? this.summaryTaskId,
    );
  }

  // 초기 상태 팩토리
  factory PipelineState.initial() {
    return const PipelineState(
      currentStep: PipelineStep.idle,
      progress: 0.0,
    );
  }
}
