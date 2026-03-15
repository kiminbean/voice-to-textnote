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
}
