import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/widgets/improved_result_badge.dart';

void main() {
  testWidgets('개선된 결과 라벨을 표시', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ImprovedResultBadge(),
        ),
      ),
    );

    expect(find.text('개선된 결과'), findsOneWidget);
    expect(find.byIcon(Icons.verified_outlined), findsOneWidget);
  });
}
