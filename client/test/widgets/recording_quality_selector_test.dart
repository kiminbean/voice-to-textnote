// RecordingQualitySelector 위젯 테스트
// SPEC-APP-005 REQ-003,004,005 — 녹음 품질 프리셋 선택 및 현재 설정 표시
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/recording_config.dart';
import 'package:voice_to_textnote/widgets/recording_quality_selector.dart';

void main() {
  group('RecordingQualitySelector', () {
    Widget buildSubject({RecordingConfig config = RecordingConfig.standard, required ValueChanged<RecordingConfig> onChanged, bool isRecording = false}) {
      return MaterialApp(
        home: Scaffold(
          body: RecordingQualitySelector(
            currentConfig: config,
            onChanged: onChanged,
            isRecording: isRecording,
          ),
        ),
      );
    }

    testWidgets('위젯이 오류 없이 렌더링되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildSubject(onChanged: (_) {}));
      expect(find.byType(RecordingQualitySelector), findsOneWidget);
    });

    testWidgets('3개 프리셋 칩이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildSubject(onChanged: (_) {}));
      expect(find.byType(ChoiceChip), findsNWidgets(3));
    });

    testWidgets('프리셋 라벨이 올바르게 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildSubject(onChanged: (_) {}));
      expect(find.text('표준'), findsOneWidget);
      expect(find.text('고품질'), findsOneWidget);
      expect(find.text('절약'), findsOneWidget);
    });

    testWidgets('선택된 항목이 표준 프리셋이어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildSubject(onChanged: (_) {}));

      final chips = tester.widgetList<ChoiceChip>(find.byType(ChoiceChip));
      final standardChip = chips.firstWhere(
        (chip) => (chip.label as Text).data == '표준',
      );
      expect(standardChip.selected, true);
    });

    testWidgets('고품질 선택 시 onChanged 콜백이 호출되어야 함', (WidgetTester tester) async {
      RecordingConfig? selectedConfig;
      await tester.pumpWidget(buildSubject(
        onChanged: (config) => selectedConfig = config,
      ));

      await tester.tap(find.text('고품질'));
      await tester.pumpAndSettle();

      expect(selectedConfig, equals(RecordingConfig.highQuality));
    });

    testWidgets('현재 설정 요약이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildSubject(
        config: RecordingConfig.highQuality,
        onChanged: (_) {},
      ));

      expect(find.textContaining('현재 설정:'), findsOneWidget);
      expect(find.textContaining('고품질'), findsWidgets);
    });

    testWidgets('녹음 중에는 잠금 아이콘이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildSubject(
        onChanged: (_) {},
        isRecording: true,
      ));

      expect(find.text('녹음 중에는 변경할 수 없습니다'), findsOneWidget);
      expect(find.byIcon(Icons.lock_outline), findsOneWidget);
    });
  });
}
