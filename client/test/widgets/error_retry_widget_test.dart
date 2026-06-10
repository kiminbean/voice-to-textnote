// ErrorRetryWidget 테스트
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/widgets/error_retry_widget.dart';

void main() {
  group('ErrorRetryWidget', () {
    // 메시지 표시 테스트
    testWidgets('오류 메시지가 표시되어야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ErrorRetryWidget(
              message: '데이터를 불러올 수 없습니다',
            ),
          ),
        ),
      );

      // Assert
      expect(find.text('데이터를 불러올 수 없습니다'), findsOneWidget);
    });

    // 재시도 버튼 표시 테스트
    testWidgets('재시도 버튼이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ErrorRetryWidget(
              message: '오류 발생',
              onRetry: () {},
            ),
          ),
        ),
      );

      expect(find.text('다시 시도'), findsOneWidget);
    });

    // 재시도 콜백 호출 테스트
    testWidgets('재시도 버튼 탭 시 onRetry가 호출되어야 함', (WidgetTester tester) async {
      // Arrange
      var retryCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ErrorRetryWidget(
              message: '오류 발생',
              onRetry: () => retryCalled = true,
            ),
          ),
        ),
      );

      // Act
      await tester.tap(find.text('다시 시도'));

      // Assert
      expect(retryCalled, isTrue);
    });

    // 오류 아이콘 표시 테스트
    testWidgets('오류 아이콘이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ErrorRetryWidget(message: '오류'),
          ),
        ),
      );

      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });
  });
}
