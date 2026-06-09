// PartialResultPanel 위젯 테스트
// SPEC-APP-005 REQ-009,010 — 완료된 단계의 결과를 즉시 표시
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/widgets/partial_result_panel.dart';

void main() {
  group('PartialResultPanel', () {
    testWidgets('빈 상태에서는 아무것도 표시하지 않아야 함', (WidgetTester tester) async {
      // Arrange
      final emptyState = PipelineState.initial();

      // Act
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PartialResultPanel(pipelineState: emptyState),
          ),
        ),
      );

      // Assert: SizedBox.shrink()가 렌더링됨 — Card가 없어야 함
      expect(find.byType(Card), findsNothing);
    });

    testWidgets('완료된 단계가 있으면 체크 아이콘과 함께 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange: STT 단계 완료
      final state = PipelineState.initial().copyWith(
        currentStep: PipelineStep.diarizing,
        stageResults: {
          PipelineStep.transcribing: StageResult(
            step: PipelineStep.transcribing,
            data: {'text': '테스트 텍스트'},
            completedAt: DateTime.now(),
          ),
        },
      );

      // Act
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PartialResultPanel(pipelineState: state),
          ),
        ),
      );

      // Assert: Card 표시 + 체크 아이콘
      expect(find.byType(Card), findsOneWidget);
      expect(find.byIcon(Icons.check_circle), findsOneWidget);
      expect(find.text('음성 인식 (STT)'), findsOneWidget);
    });

    testWidgets('실패한 단계가 있으면 에러 아이콘과 재시도 버튼이 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange: STT 단계 실패
      final state = PipelineState.initial().copyWith(
        currentStep: PipelineStep.failed,
        stageErrors: {
          PipelineStep.transcribing: '업로드 실패',
        },
        failedStep: PipelineStep.transcribing,
      );

      // Act
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PartialResultPanel(
              pipelineState: state,
              onRetryFailed: () {},
            ),
          ),
        ),
      );

      // Assert: 에러 아이콘 + 재시도 버튼
      expect(find.byIcon(Icons.error), findsOneWidget);
      expect(find.text('재시도'), findsOneWidget);
      expect(find.text('음성 인식 (STT)'), findsOneWidget);
    });

    testWidgets('재시도 버튼 탭 시 onRetryFailed 콜백이 호출되어야 함',
        (WidgetTester tester) async {
      // Arrange
      var retryCalled = false;
      final state = PipelineState.initial().copyWith(
        currentStep: PipelineStep.failed,
        stageErrors: {
          PipelineStep.uploading: '네트워크 오류',
        },
        failedStep: PipelineStep.uploading,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PartialResultPanel(
              pipelineState: state,
              onRetryFailed: () => retryCalled = true,
            ),
          ),
        ),
      );

      // Act
      await tester.tap(find.text('재시도'));
      await tester.pumpAndSettle();

      // Assert
      expect(retryCalled, true);
    });

    testWidgets('완료된 단계와 실패한 단계가 동시에 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange: 업로드 완료 + STT 실패
      final state = PipelineState.initial().copyWith(
        currentStep: PipelineStep.failed,
        stageResults: {
          PipelineStep.uploading: StageResult(
            step: PipelineStep.uploading,
            data: null,
            completedAt: DateTime.now(),
          ),
        },
        stageErrors: {
          PipelineStep.transcribing: 'STT 서비스 오류',
        },
        failedStep: PipelineStep.transcribing,
      );

      // Act
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PartialResultPanel(
              pipelineState: state,
              onRetryFailed: () {},
            ),
          ),
        ),
      );

      // Assert
      expect(find.text('업로드'), findsOneWidget);
      expect(find.text('음성 인식 (STT)'), findsOneWidget);
      expect(find.byIcon(Icons.check_circle), findsOneWidget);
      expect(find.byIcon(Icons.error), findsOneWidget);
    });

    testWidgets('단계별 결과 제목이 표시되어야 함', (WidgetTester tester) async {
      // Arrange
      final state = PipelineState.initial().copyWith(
        currentStep: PipelineStep.completed,
        stageResults: {
          PipelineStep.uploading: StageResult(
            step: PipelineStep.uploading,
            data: null,
            completedAt: DateTime.now(),
          ),
        },
      );

      // Act
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PartialResultPanel(pipelineState: state),
          ),
        ),
      );

      // Assert: 패널 제목
      expect(find.text('단계별 결과'), findsOneWidget);
    });
  });
}
