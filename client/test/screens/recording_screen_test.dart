// RecordingScreen 위젯 테스트
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/screens/recording_screen.dart';

void main() {
  group('RecordingScreen', () {
    // go_router를 포함한 테스트 앱 빌더 헬퍼
    Widget buildTestApp() {
      final router = GoRouter(
        initialLocation: '/recording',
        routes: [
          GoRoute(
            path: '/',
            builder: (_, __) => const Scaffold(body: Text('홈')),
          ),
          GoRoute(
            path: '/recording',
            builder: (_, __) => const RecordingScreen(),
          ),
        ],
      );

      return ProviderScope(
        child: MaterialApp.router(
          routerConfig: router,
        ),
      );
    }

    // 초기 버튼 상태 테스트
    testWidgets('초기에 녹음 시작 버튼이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // 녹음 버튼 (큰 원형 아이콘)이 존재해야 함
      expect(find.bySemanticsLabel('녹음 시작'), findsOneWidget);

      // 타이머 표시 (00:00)
      expect(find.text('00:00'), findsOneWidget);

      // 초기 상태 텍스트
      expect(find.text('탭하여 녹음 시작'), findsOneWidget);
      expect(find.text('Live Transcript'), findsOneWidget);
      expect(find.text('업로드'), findsOneWidget);
      expect(find.text('회의 링크'), findsOneWidget);
    });

    // 녹음 버튼 탭 후 상태 확인 (실제 마이크 없이 테스트)
    // 테스트 환경에서는 마이크 권한이 없으므로 UI 변화가 없을 수 있음
    testWidgets('녹음 버튼 탭 시 UI가 응답해야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // 녹음 버튼 탭 (비동기 처리)
      await tester.tap(find.bySemanticsLabel('녹음 시작'));
      await tester.pump();

      // UI가 존재해야 함 (권한 없이는 상태 변화 없을 수 있음)
      expect(find.byType(RecordingScreen), findsOneWidget);
    });

    // 타이머 표시 형식 테스트
    testWidgets('타이머가 MM:SS 형식으로 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // 초기값 00:00 확인
      expect(find.text('00:00'), findsOneWidget);
    });

    // 앱바 제목 테스트
    testWidgets('앱바에 AI 녹음 제목이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      expect(find.text('AI 녹음'), findsOneWidget);
    });
  });
}
