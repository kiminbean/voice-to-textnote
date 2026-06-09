// PipelineState 모델 테스트
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';

void main() {
  group('PipelineState 모델', () {
    // 기본 생성 테스트
    test('PipelineState 기본 생성이 올바르게 동작해야 함', () {
      const state = PipelineState(
        currentStep: PipelineStep.idle,
        progress: 0.0,
      );

      expect(state.currentStep, PipelineStep.idle);
      expect(state.progress, 0.0);
      expect(state.errorMessage, isNull);
      expect(state.currentTaskId, isNull);
    });

    // 진행 중 상태 생성 테스트
    test('진행 중 PipelineState 생성이 올바르게 동작해야 함', () {
      const state = PipelineState(
        currentStep: PipelineStep.transcribing,
        progress: 0.5,
        currentTaskId: 'stt-task-001',
      );

      expect(state.currentStep, PipelineStep.transcribing);
      expect(state.progress, 0.5);
      expect(state.currentTaskId, 'stt-task-001');
      expect(state.errorMessage, isNull);
    });

    // 실패 상태 생성 테스트
    test('실패 PipelineState 생성이 올바르게 동작해야 함', () {
      const state = PipelineState(
        currentStep: PipelineStep.failed,
        progress: 0.3,
        errorMessage: '서버 연결 오류',
      );

      expect(state.currentStep, PipelineStep.failed);
      expect(state.errorMessage, '서버 연결 오류');
    });

    // copyWith 테스트
    test('copyWith가 올바르게 동작해야 함', () {
      const original = PipelineState(
        currentStep: PipelineStep.uploading,
        progress: 0.1,
      );

      final updated = original.copyWith(
        currentStep: PipelineStep.transcribing,
        progress: 0.4,
        currentTaskId: 'stt-task-002',
      );

      expect(updated.currentStep, PipelineStep.transcribing);
      expect(updated.progress, 0.4);
      expect(updated.currentTaskId, 'stt-task-002');
      // 변경되지 않은 필드
      expect(updated.errorMessage, isNull);
    });

    // 파이프라인 단계 순서 테스트
    test('PipelineStep이 올바른 순서로 정의되어야 함', () {
      expect(PipelineStep.values, containsAll([
        PipelineStep.idle,
        PipelineStep.uploading,
        PipelineStep.transcribing,
        PipelineStep.diarizing,
        PipelineStep.generatingMinutes,
        PipelineStep.summarizing,
        PipelineStep.completed,
        PipelineStep.failed,
      ]));
    });

    // 진행률 범위 테스트
    test('진행률은 0.0에서 1.0 사이여야 함', () {
      const states = [
        PipelineState(currentStep: PipelineStep.idle, progress: 0.0),
        PipelineState(currentStep: PipelineStep.uploading, progress: 0.1),
        PipelineState(currentStep: PipelineStep.transcribing, progress: 0.3),
        PipelineState(currentStep: PipelineStep.completed, progress: 1.0),
      ];

      for (final state in states) {
        expect(state.progress, greaterThanOrEqualTo(0.0));
        expect(state.progress, lessThanOrEqualTo(1.0));
      }
    });
  });

  // SPEC-APP-005: 단계별 결과/타이밍/에러 추적 필드 테스트
  group('PipelineState SPEC-APP-005 단계별 추적', () {
    final fixedNow = DateTime(2026, 6, 9, 12, 0, 0);

    test('initial 팩토리는 빈 맵과 null failedStep을 가져야 함', () {
      final state = PipelineState.initial();

      expect(state.stageResults, isEmpty);
      expect(state.stageTimings, isEmpty);
      expect(state.stageErrors, isEmpty);
      expect(state.failedStep, isNull);
    });

    test('stageResults 맵이 올바르게 생성되어야 함', () {
      final result = StageResult(
        step: PipelineStep.transcribing,
        data: {'text': '인식된 텍스트'},
        completedAt: fixedNow,
      );

      final state = PipelineState(
        currentStep: PipelineStep.diarizing,
        progress: 0.6,
        stageResults: {PipelineStep.transcribing: result},
      );

      expect(state.stageResults, contains(PipelineStep.transcribing));
      expect(state.stageResults[PipelineStep.transcribing]!.data,
          {'text': '인식된 텍스트'});
      expect(state.stageResults[PipelineStep.transcribing]!.completedAt,
          fixedNow);
    });

    test('stageTimings 맵이 올바르게 생성되어야 함', () {
      final timing = StageTiming(
        step: PipelineStep.uploading,
        duration: const Duration(seconds: 5),
        startedAt: fixedNow.subtract(const Duration(seconds: 5)),
        completedAt: fixedNow,
      );

      final state = PipelineState(
        currentStep: PipelineStep.transcribing,
        progress: 0.4,
        stageTimings: {PipelineStep.uploading: timing},
      );

      expect(state.stageTimings, contains(PipelineStep.uploading));
      expect(state.stageTimings[PipelineStep.uploading]!.duration,
          const Duration(seconds: 5));
    });

    test('stageErrors 맵이 올바르게 생성되어야 함', () {
      const state = PipelineState(
        currentStep: PipelineStep.failed,
        progress: 0.3,
        stageErrors: {PipelineStep.transcribing: 'STT 서비스 타임아웃'},
      );

      expect(state.stageErrors, contains(PipelineStep.transcribing));
      expect(state.stageErrors[PipelineStep.transcribing], 'STT 서비스 타임아웃');
    });

    test('failedStep 필드가 올바르게 설정되어야 함', () {
      const state = PipelineState(
        currentStep: PipelineStep.failed,
        progress: 0.3,
        failedStep: PipelineStep.diarizing,
      );

      expect(state.failedStep, PipelineStep.diarizing);
    });

    test('hasStageResult가 올바른 결과를 반환해야 함', () {
      final result = StageResult(
        step: PipelineStep.summarizing,
        data: '요약 내용',
        completedAt: fixedNow,
      );

      final state = PipelineState(
        currentStep: PipelineStep.completed,
        progress: 1.0,
        stageResults: {PipelineStep.summarizing: result},
      );

      expect(state.hasStageResult(PipelineStep.summarizing), isTrue);
      expect(state.hasStageResult(PipelineStep.transcribing), isFalse);
    });

    test('isStepFailed가 올바른 결과를 반환해야 함', () {
      const state = PipelineState(
        currentStep: PipelineStep.failed,
        progress: 0.3,
        stageErrors: {
          PipelineStep.transcribing: '에러1',
          PipelineStep.diarizing: '에러2',
        },
      );

      expect(state.isStepFailed(PipelineStep.transcribing), isTrue);
      expect(state.isStepFailed(PipelineStep.diarizing), isTrue);
      expect(state.isStepFailed(PipelineStep.uploading), isFalse);
    });

    test('canRetry getter가 올바른 결과를 반환해야 함', () {
      // failedStep이 null이면 재시도 불가
      const noRetryState = PipelineState(
        currentStep: PipelineStep.failed,
        progress: 0.3,
      );
      expect(noRetryState.canRetry, isFalse);

      // failedStep이 설정되면 재시도 가능
      const retryState = PipelineState(
        currentStep: PipelineStep.failed,
        progress: 0.3,
        failedStep: PipelineStep.transcribing,
      );
      expect(retryState.canRetry, isTrue);
    });

    test('getStageDuration이 올바른 Duration을 반환해야 함', () {
      final timing = StageTiming(
        step: PipelineStep.uploading,
        duration: const Duration(milliseconds: 3500),
        startedAt: fixedNow.subtract(const Duration(milliseconds: 3500)),
        completedAt: fixedNow,
      );

      final state = PipelineState(
        currentStep: PipelineStep.transcribing,
        progress: 0.4,
        stageTimings: {PipelineStep.uploading: timing},
      );

      expect(state.getStageDuration(PipelineStep.uploading),
          const Duration(milliseconds: 3500));
      expect(state.getStageDuration(PipelineStep.transcribing), isNull);
    });

    test('copyWith로 stageResults를 업데이트할 수 있어야 함', () {
      const original = PipelineState(
        currentStep: PipelineStep.transcribing,
        progress: 0.3,
      );

      final newResult = StageResult(
        step: PipelineStep.uploading,
        data: {'url': 'https://example.com/file.wav'},
        completedAt: fixedNow,
      );

      final updated = original.copyWith(
        stageResults: {PipelineStep.uploading: newResult},
      );

      expect(updated.stageResults, contains(PipelineStep.uploading));
      expect(updated.currentStep, PipelineStep.transcribing);
    });

    test('copyWith로 stageTimings를 업데이트할 수 있어야 함', () {
      const original = PipelineState(
        currentStep: PipelineStep.transcribing,
        progress: 0.3,
      );

      final newTiming = StageTiming(
        step: PipelineStep.uploading,
        duration: const Duration(seconds: 2),
        startedAt: fixedNow.subtract(const Duration(seconds: 2)),
        completedAt: fixedNow,
      );

      final updated = original.copyWith(
        stageTimings: {PipelineStep.uploading: newTiming},
      );

      expect(updated.stageTimings, contains(PipelineStep.uploading));
      expect(updated.stageTimings[PipelineStep.uploading]!.duration,
          const Duration(seconds: 2));
    });

    test('copyWith로 stageErrors를 업데이트할 수 있어야 함', () {
      const original = PipelineState(
        currentStep: PipelineStep.failed,
        progress: 0.3,
      );

      final updated = original.copyWith(
        stageErrors: {PipelineStep.transcribing: '네트워크 오류'},
      );

      expect(updated.stageErrors, contains(PipelineStep.transcribing));
      expect(updated.stageErrors[PipelineStep.transcribing], '네트워크 오류');
    });

    test('copyWith의 clearFailedStep이 true면 failedStep이 null이어야 함', () {
      const original = PipelineState(
        currentStep: PipelineStep.failed,
        progress: 0.3,
        failedStep: PipelineStep.diarizing,
      );

      final cleared = original.copyWith(clearFailedStep: true);

      expect(cleared.failedStep, isNull);
    });

    test('copyWith에서 clearFailedStep이 false면 failedStep이 유지되어야 함', () {
      const original = PipelineState(
        currentStep: PipelineStep.failed,
        progress: 0.3,
        failedStep: PipelineStep.diarizing,
      );

      final kept = original.copyWith(progress: 0.5);

      expect(kept.failedStep, PipelineStep.diarizing);
    });

    test('StageResult 생성자가 모든 필드를 올바르게 설정해야 함', () {
      final result = StageResult(
        step: PipelineStep.generatingMinutes,
        data: [1, 2, 3],
        completedAt: fixedNow,
      );

      expect(result.step, PipelineStep.generatingMinutes);
      expect(result.data, [1, 2, 3]);
      expect(result.completedAt, fixedNow);
    });

    test('StageTiming 생성자가 모든 필드를 올바르게 설정해야 함', () {
      final timing = StageTiming(
        step: PipelineStep.summarizing,
        duration: const Duration(seconds: 10),
        startedAt: fixedNow.subtract(const Duration(seconds: 10)),
        completedAt: fixedNow,
      );

      expect(timing.step, PipelineStep.summarizing);
      expect(timing.duration, const Duration(seconds: 10));
      expect(timing.startedAt, fixedNow.subtract(const Duration(seconds: 10)));
      expect(timing.completedAt, fixedNow);
    });
  });
}
