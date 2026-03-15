// RecordingScreen 위젯 테스트
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/screens/recording_screen.dart';

void main() {
  group('RecordingScreen', () {
    // 초기 버튼 상태 테스트
    testWidgets('초기에 녹음 시작 버튼이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
            home: RecordingScreen(),
          ),
        ),
      );

      // 녹음 버튼 (큰 원형 아이콘)이 존재해야 함
      expect(find.byIcon(Icons.mic), findsOneWidget);

      // 타이머 표시 (00:00)
      expect(find.text('00:00'), findsOneWidget);

      // 초기 상태 텍스트
      expect(find.text('탭하여 녹음 시작'), findsOneWidget);
    });

    // 녹음 중 상태 텍스트 변경 테스트
    testWidgets('녹음 버튼 탭 시 상태가 변경되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
            home: RecordingScreen(),
          ),
        ),
      );

      // 녹음 버튼 탭
      await tester.tap(find.byIcon(Icons.mic));
      await tester.pump();

      // 녹음 중 상태 표시 확인
      expect(find.text('녹음 중...'), findsOneWidget);
    });
  });
}
