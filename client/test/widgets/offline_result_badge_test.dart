import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/widgets/offline_result_badge.dart';

void main() {
  testWidgets('오프라인 처리됨 라벨을 표시', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: OfflineResultBadge(),
        ),
      ),
    );

    expect(find.text('오프라인 처리됨'), findsOneWidget);
    expect(find.byIcon(Icons.cloud_off_outlined), findsOneWidget);
  });

  testWidgets('재처리 콜백이 있으면 refresh 버튼을 표시하고 호출', (tester) async {
    var tapped = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: OfflineResultBadge(
            onRetry: () => tapped = true,
          ),
        ),
      ),
    );

    await tester.tap(find.byTooltip('온라인 재처리'));
    await tester.pump();

    expect(tapped, isTrue);
  });
}
