// 홈 화면 게스트 배너 테스트
// SPEC-GUEST-001: 게스트 모드 배너 표시/숨김 확인
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/models/auth_user.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/providers/connectivity_provider.dart';
import 'package:voice_to_textnote/screens/home_screen.dart';
import 'package:voice_to_textnote/services/auth_api.dart';
import 'package:voice_to_textnote/services/auth_service.dart';
import 'package:voice_to_textnote/services/connectivity_service.dart';
import 'package:voice_to_textnote/services/history_api.dart';

// Mock 클래스
class MockAuthApi extends Mock implements AuthApi {}

class MockAuthService extends Mock implements AuthService {}

class MockConnectivityService extends Mock implements ConnectivityService {}

class MockHistoryApi extends Mock implements HistoryApi {}

// 온라인 상태 Override 헬퍼
List<Override> _connectivityOverrides(MockConnectivityService mockService) {
  final streamController = StreamController<bool>.broadcast();
  final historyApi = MockHistoryApi();
  when(() => mockService.isOnline).thenReturn(true);
  when(() => mockService.onStatusChange)
      .thenAnswer((_) => streamController.stream);
  when(() => mockService.startMonitoring(
        interval: any(named: 'interval'),
      )).thenReturn(null);
  when(() => mockService.dispose()).thenReturn(null);
  when(() => historyApi.list(
        taskType: any(named: 'taskType'),
        status: any(named: 'status'),
        page: any(named: 'page'),
        pageSize: any(named: 'pageSize'),
      )).thenAnswer(
    (_) async => {
      'items': [],
      'total': 0,
      'page': 1,
      'page_size': 20,
    },
  );

  return [
    connectivityServiceProvider.overrideWithValue(mockService),
    historyApiProvider.overrideWithValue(historyApi),
  ];
}

// 테스트용 앱 빌더 - GoRouter 포함
Widget _buildTestApp({required List<Override> overrides}) {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (_, __) => const HomeScreen(),
      ),
      GoRoute(
        path: '/register',
        builder: (_, __) => const Scaffold(body: Text('회원가입')),
      ),
      GoRoute(
        path: '/recording',
        builder: (_, __) => const Scaffold(body: Text('녹음')),
      ),
      GoRoute(
        path: '/teams',
        builder: (_, __) => const Scaffold(body: Text('팀')),
      ),
      GoRoute(
        path: '/search',
        builder: (_, __) => const Scaffold(body: Text('검색')),
      ),
      GoRoute(
        path: '/templates',
        builder: (_, __) => const Scaffold(body: Text('양식')),
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
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    registerFallbackValue(const Duration(seconds: 30));
  });

  group('HomeScreen 게스트 배너', () {
    late MockAuthApi mockAuthApi;
    late MockAuthService mockAuthService;
    late MockConnectivityService mockConnectivity;

    setUp(() {
      SharedPreferences.setMockInitialValues({});
      mockAuthApi = MockAuthApi();
      mockAuthService = MockAuthService();
      mockConnectivity = MockConnectivityService();
      when(() => mockAuthService.getAccessToken())
          .thenAnswer((_) async => null);
      when(() => mockAuthService.getGuestToken()).thenAnswer((_) async => null);
      when(() => mockAuthService.getGuestSessionId())
          .thenAnswer((_) async => null);
    });

    // 게스트 모드일 때 배너 표시 확인
    testWidgets('게스트 상태일 때 게스트 배너가 표시되어야 함', (tester) async {
      final connectivityOverrides = _connectivityOverrides(mockConnectivity);

      await tester.pumpWidget(
        _buildTestApp(
          overrides: [
            ...connectivityOverrides,
            authServiceProvider.overrideWithValue(mockAuthService),
            authStateProvider.overrideWith(
              (ref) {
                final notifier = AuthNotifier(mockAuthApi, mockAuthService);
                // 초기 상태를 게스트로 설정
                notifier.setGuestStateForTest();
                return notifier;
              },
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // "게스트 모드" 텍스트가 화면에 표시되어야 함
      expect(find.textContaining('게스트 모드'), findsOneWidget);
    });

    // 인증된 사용자는 배너가 표시되지 않아야 함
    testWidgets('인증된 상태일 때 게스트 배너가 숨겨져야 함', (tester) async {
      final connectivityOverrides = _connectivityOverrides(mockConnectivity);
      const testUser = AuthUser(
        id: 'user-001',
        email: 'test@example.com',
        displayName: '테스트 사용자',
        isActive: true,
      );

      await tester.pumpWidget(
        _buildTestApp(
          overrides: [
            ...connectivityOverrides,
            authServiceProvider.overrideWithValue(mockAuthService),
            authStateProvider.overrideWith(
              (ref) {
                final notifier = AuthNotifier(mockAuthApi, mockAuthService);
                notifier.setAuthenticatedStateForTest(testUser);
                return notifier;
              },
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // "게스트 모드" 텍스트가 없어야 함
      expect(find.textContaining('게스트 모드'), findsNothing);
    });

    // 게스트 배너에 24시간 경고 메시지 확인
    testWidgets('게스트 배너에 24시간 안내 텍스트가 표시되어야 함', (tester) async {
      final connectivityOverrides = _connectivityOverrides(mockConnectivity);

      await tester.pumpWidget(
        _buildTestApp(
          overrides: [
            ...connectivityOverrides,
            authServiceProvider.overrideWithValue(mockAuthService),
            authStateProvider.overrideWith(
              (ref) {
                final notifier = AuthNotifier(mockAuthApi, mockAuthService);
                notifier.setGuestStateForTest();
                return notifier;
              },
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // "24시간" 텍스트가 배너에 표시되어야 함
      expect(find.textContaining('24시간'), findsOneWidget);
    });
  });
}
