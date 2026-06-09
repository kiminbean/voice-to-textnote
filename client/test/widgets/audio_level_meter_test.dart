// AudioLevelMeter 위젯 테스트
// SPEC-APP-005 REQ-002 — 0~100% 실시간 오디오 레벨 시각화
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/widgets/audio_level_meter.dart';

void main() {
  group('AudioLevelMeter', () {
    testWidgets('위젯이 오류 없이 렌더링되어야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AudioLevelMeter(level: 0.5),
          ),
        ),
      );

      // Assert
      expect(find.byType(AudioLevelMeter), findsOneWidget);
    });

    testWidgets('level=0일 때 0% 텍스트가 표시되어야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AudioLevelMeter(level: 0.0),
          ),
        ),
      );

      // Assert
      expect(find.text('0%'), findsOneWidget);
    });

    testWidgets('level=1일 때 100% 텍스트가 표시되어야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AudioLevelMeter(level: 1.0),
          ),
        ),
      );

      // Assert
      expect(find.text('100%'), findsOneWidget);
    });

    testWidgets('isActive=false일 때 0%로 표시되어야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AudioLevelMeter(level: 0.8, isActive: false),
          ),
        ),
      );

      // Assert: 비활성화 시 displayLevel이 0.0이므로 0%
      expect(find.text('0%'), findsOneWidget);
    });

    testWidgets('커스텀 height가 적용되어야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AudioLevelMeter(level: 0.5, height: 16.0),
          ),
        ),
      );

      // Assert: height=16.0인 SizedBox가 존재하는지 확인
      final sizedBox = tester.widget<SizedBox>(
        find.ancestor(
          of: find.byType(Stack),
          matching: find.byType(SizedBox),
        ),
      );
      expect(sizedBox.height, 16.0);
    });

    testWidgets('중간 레벨 값이 올바른 퍼센트로 표시되어야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AudioLevelMeter(level: 0.75),
          ),
        ),
      );

      // Assert: 0.75 * 100 = 75%
      expect(find.text('75%'), findsOneWidget);
    });
  });
}
