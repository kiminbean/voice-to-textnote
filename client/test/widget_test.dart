// 기본 Flutter 위젯 스모크 테스트
// voice_to_textnote 앱이 정상적으로 렌더링되는지 확인
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/screens/home_screen.dart';

void main() {
  testWidgets('앱 기본 렌더링 스모크 테스트', (WidgetTester tester) async {
    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (_, __) => const HomeScreen(),
        ),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(
          routerConfig: router,
        ),
      ),
    );

    // HomeScreen의 주기적 타이머(서버 동기화 등)로 pumpAndSettle 타임아웃 방지
    await tester.pump(const Duration(seconds: 1));

    // 홈 화면이 렌더링되어야 함
    expect(find.byType(HomeScreen), findsOneWidget);
  });
}
