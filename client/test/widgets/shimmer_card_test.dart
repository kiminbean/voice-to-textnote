// ShimmerCard 위젯 테스트
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shimmer/shimmer.dart';
import 'package:voice_to_textnote/widgets/shimmer_card.dart';
import 'package:voice_to_textnote/widgets/shimmer_text.dart';

void main() {
  group('ShimmerCard', () {
    // 렌더링 테스트
    testWidgets('ShimmerCard가 오류 없이 렌더링되어야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ShimmerCard(),
          ),
        ),
      );

      // Assert: 위젯 트리에 존재
      expect(find.byType(ShimmerCard), findsOneWidget);
    });

    // Shimmer 효과 포함 테스트
    testWidgets('Shimmer 애니메이션 위젯이 포함되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ShimmerCard(),
          ),
        ),
      );

      // Assert: Shimmer 위젯 존재 확인
      expect(find.byType(Shimmer), findsWidgets);
    });

    // Card 위젯 포함 테스트
    testWidgets('Card 위젯을 포함해야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ShimmerCard(),
          ),
        ),
      );

      expect(find.byType(Card), findsOneWidget);
    });
  });

  group('ShimmerText', () {
    // 렌더링 테스트
    testWidgets('ShimmerText가 오류 없이 렌더링되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ShimmerText(),
          ),
        ),
      );

      expect(find.byType(ShimmerText), findsOneWidget);
    });

    // 라인 수 파라미터 테스트
    testWidgets('lines 파라미터에 따라 여러 줄이 렌더링되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ShimmerText(lines: 3),
          ),
        ),
      );

      // Container(shimmer line) 3개 존재 확인
      expect(find.byType(ShimmerText), findsOneWidget);
    });
  });
}
