// 로그인 화면 게스트 버튼 테스트
// SPEC-GUEST-001: 게스트로 시작 버튼 UI 확인
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/screens/login_screen.dart';
import 'package:voice_to_textnote/services/auth_api.dart';
import 'package:voice_to_textnote/services/auth_service.dart';

// Mock 클래스
class MockAuthApi extends Mock implements AuthApi {}
class MockAuthService extends Mock implements AuthService {}

// 테스트용 GoRouter 래퍼
Widget _buildTestApp({List<Override> overrides = const []}) {
  final router = GoRouter(
    initialLocation: '/login',
    routes: [
      GoRoute(
        path: '/login',
        builder: (_, __) => const LoginScreen(),
      ),
      GoRoute(
        path: '/',
        builder: (_, __) => const Scaffold(body: Text('홈')),
      ),
      GoRoute(
        path: '/register',
        builder: (_, __) => const Scaffold(body: Text('회원가입')),
      ),
    ],
  );

  return ProviderScope(
    overrides: overrides,
    child: MaterialApp.router(
      routerConfig: router,
    ),
  );
}

void main() {
  group('LoginScreen 게스트 버튼', () {
    late MockAuthApi mockAuthApi;
    late MockAuthService mockAuthService;

    setUp(() {
      mockAuthApi = MockAuthApi();
      mockAuthService = MockAuthService();
    });

    // 게스트 버튼 존재 여부 확인
    testWidgets('게스트로 시작 버튼이 화면에 존재해야 함', (tester) async {
      await tester.pumpWidget(
        _buildTestApp(
          overrides: [
            authStateProvider.overrideWith(
              (ref) => AuthNotifier(mockAuthApi, mockAuthService),
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // 게스트 버튼을 찾는 여러 방법 시도
      final guestButtonFinder = find.textContaining('게스트');
      expect(guestButtonFinder, findsOneWidget);
    });

    // 게스트 버튼 텍스트 확인
    testWidgets('게스트 버튼에 올바른 텍스트가 표시되어야 함', (tester) async {
      await tester.pumpWidget(
        _buildTestApp(
          overrides: [
            authStateProvider.overrideWith(
              (ref) => AuthNotifier(mockAuthApi, mockAuthService),
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // "24시간"이 포함된 텍스트 확인
      final guestText = find.textContaining('24시간');
      expect(guestText, findsOneWidget);
    });

    // 게스트 버튼 탭 시 API 호출 확인
    testWidgets('게스트 버튼 탭 시 startAsGuest가 호출되어야 함', (tester) async {
      when(() => mockAuthApi.createGuestSession()).thenAnswer(
        (_) async => {
          'guest_session_id': 'session-123',
          'guest_token': 'test-token',
          'expires_at': '2026-03-30T00:00:00Z',
        },
      );
      when(
        () => mockAuthService.saveGuestToken(any(), any()),
      ).thenAnswer((_) async {});

      await tester.pumpWidget(
        _buildTestApp(
          overrides: [
            authStateProvider.overrideWith(
              (ref) => AuthNotifier(mockAuthApi, mockAuthService),
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // 게스트 버튼 탭
      final guestButton = find.textContaining('게스트');
      await tester.tap(guestButton);
      await tester.pumpAndSettle();

      // createGuestSession이 호출되었는지 확인
      verify(() => mockAuthApi.createGuestSession()).called(1);
    });
  });
}
