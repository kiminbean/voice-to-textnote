// ErrorDialog 위젯 테스트
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/widgets/error_dialog.dart';

void main() {
  group('ErrorDialog', () {
    // 메시지 표시 테스트
    testWidgets('오류 메시지가 표시되어야 함', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => showDialog(
                  context: context,
                  builder: (_) => const ErrorDialog(
                    message: '서버에 연결할 수 없습니다',
                  ),
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('열기'));
      await tester.pumpAndSettle();

      // Assert
      expect(find.text('서버에 연결할 수 없습니다'), findsOneWidget);
      expect(find.text('오류'), findsOneWidget);
    });

    // 재시도 버튼 콜백 테스트
    testWidgets('재시도 버튼 탭 시 onRetry 콜백이 호출되어야 함', (WidgetTester tester) async {
      // Arrange
      var retryCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => showDialog(
                  context: context,
                  builder: (_) => ErrorDialog(
                    message: '오류가 발생했습니다',
                    onRetry: () => retryCalled = true,
                  ),
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('열기'));
      await tester.pumpAndSettle();

      // Act: 재시도 버튼 탭
      await tester.tap(find.text('재시도'));
      await tester.pumpAndSettle();

      // Assert
      expect(retryCalled, isTrue);
    });

    // 홈으로 버튼 표시 테스트
    testWidgets('onGoHome 제공 시 홈으로 버튼이 표시되어야 함', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => showDialog(
                  context: context,
                  builder: (_) => ErrorDialog(
                    message: '처리 실패',
                    onGoHome: () {},
                  ),
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('열기'));
      await tester.pumpAndSettle();

      // Assert
      expect(find.text('홈으로'), findsOneWidget);
    });

    // onRetry 없을 때 재시도 버튼 미표시 테스트
    testWidgets('onRetry 없을 때 재시도 버튼이 표시되지 않아야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => showDialog(
                  context: context,
                  builder: (_) => const ErrorDialog(
                    message: '오류 메시지',
                  ),
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('열기'));
      await tester.pumpAndSettle();

      // Assert
      expect(find.text('재시도'), findsNothing);
    });
  });
}
