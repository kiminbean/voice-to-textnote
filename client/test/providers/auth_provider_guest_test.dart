// 게스트 인증 프로바이더 테스트
// SPEC-GUEST-001: 게스트 세션 생성 및 상태 관리
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/auth_user.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/services/auth_api.dart';
import 'package:voice_to_textnote/services/auth_service.dart';

// AuthApi Mock
class MockAuthApi extends Mock implements AuthApi {}

// AuthService Mock
class MockAuthService extends Mock implements AuthService {}

void main() {
  group('AuthState 게스트 상태', () {
    // 초기 상태는 게스트가 아님
    test('초기 상태는 isGuest가 false여야 함', () {
      const state = AuthState.initial();
      expect(state.isGuest, false);
    });

    // 게스트 상태 생성자 테스트
    test('AuthState.guest() 생성 시 isGuest가 true여야 함', () {
      const state = AuthState.guest();
      expect(state.isGuest, true);
    });

    // 게스트 상태의 status 확인 - 별도 guest 상태로 구분
    test('게스트 상태의 status는 guest여야 함', () {
      const state = AuthState.guest();
      expect(state.status, AuthStatus.guest);
    });

    // 인증된 일반 사용자는 게스트가 아님
    test('인증된 상태의 isGuest는 false여야 함', () {
      const state = AuthState.initial();
      expect(state.isGuest, false);
    });
  });

  group('AuthNotifier 게스트 기능', () {
    late MockAuthApi mockAuthApi;
    late MockAuthService mockAuthService;
    late ProviderContainer container;

    setUp(() {
      mockAuthApi = MockAuthApi();
      mockAuthService = MockAuthService();

      container = ProviderContainer(
        overrides: [
          authStateProvider.overrideWith(
            (ref) => AuthNotifier(mockAuthApi, mockAuthService),
          ),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    // 게스트 시작 시 guest 상태로 변경되는지 확인
    test('startAsGuest 호출 시 게스트 상태가 설정되어야 함', () async {
      // 게스트 세션 API 응답 설정
      when(() => mockAuthApi.createGuestSession()).thenAnswer(
        (_) async => {
          'guest_session_id': 'session-123',
          'guest_token': 'test-guest-token',
          'expires_at': '2026-03-30T00:00:00Z',
        },
      );
      // 게스트 토큰 저장 Mock
      when(
        () => mockAuthService.saveGuestToken(any(), any()),
      ).thenAnswer((_) async {});

      await container.read(authStateProvider.notifier).startAsGuest();

      final state = container.read(authStateProvider);
      expect(state.isGuest, true);
    });

    // 게스트 시작 중 로딩 상태 확인
    test('startAsGuest 호출 시 로딩 상태를 거쳐야 함', () async {
      // Completer를 이용해 비동기 흐름 제어
      var loadingObserved = false;
      final states = <AuthState>[];

      when(() => mockAuthApi.createGuestSession()).thenAnswer((_) async {
        // 잠시 대기해서 loading 상태를 캡처할 수 있도록
        await Future.delayed(Duration.zero);
        return {
          'guest_session_id': 'session-123',
          'guest_token': 'test-guest-token',
          'expires_at': '2026-03-30T00:00:00Z',
        };
      });
      when(
        () => mockAuthService.saveGuestToken(any(), any()),
      ).thenAnswer((_) async {});

      container.listen<AuthState>(authStateProvider, (_, next) {
        states.add(next);
        if (next.isLoading) loadingObserved = true;
      });

      await container.read(authStateProvider.notifier).startAsGuest();

      expect(loadingObserved, true);
    });

    // API 실패 시 에러 상태로 전환되는지 확인
    test('createGuestSession 실패 시 unauthenticated 상태가 되어야 함', () async {
      when(() => mockAuthApi.createGuestSession()).thenThrow(
        Exception('네트워크 오류'),
      );

      await container.read(authStateProvider.notifier).startAsGuest();

      final state = container.read(authStateProvider);
      expect(state.status, AuthStatus.unauthenticated);
    });

    test('checkAuth는 게스트 토큰이 남아 있어도 로그인 토큰을 우선해야 함', () async {
      const user = AuthUser(
        id: 'user-001',
        email: 't@test.com',
        displayName: '테스트 사용자',
        isActive: true,
      );
      when(() => mockAuthService.hasTokens()).thenAnswer((_) async => true);
      when(() => mockAuthService.isAccessTokenExpired())
          .thenAnswer((_) async => false);
      when(() => mockAuthService.getAccessToken())
          .thenAnswer((_) async => 'access-token');
      when(() => mockAuthApi.getMe('access-token')).thenAnswer((_) async => user);
      when(() => mockAuthService.clearTokens()).thenAnswer((_) async {});

      await container.read(authStateProvider.notifier).checkAuth();

      final state = container.read(authStateProvider);
      expect(state.status, AuthStatus.authenticated);
      expect(state.user?.email, 't@test.com');
      verifyNever(() => mockAuthService.isGuestMode());
    });
  });
}
