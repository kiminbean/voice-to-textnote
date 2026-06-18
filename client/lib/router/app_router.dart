// 앱 라우터 설정 (go_router 사용)
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/screens/home_screen.dart';
import 'package:voice_to_textnote/screens/login_screen.dart';
import 'package:voice_to_textnote/screens/processing_screen.dart';
import 'package:voice_to_textnote/screens/recording_screen.dart';
import 'package:voice_to_textnote/screens/register_screen.dart';
import 'package:voice_to_textnote/screens/result_screen.dart';
import 'package:voice_to_textnote/screens/settings_screen.dart';
// SPEC-TMPL-001: 양식 관리 화면 추가
import 'package:voice_to_textnote/screens/template_screen.dart';
import 'package:voice_to_textnote/screens/vocabulary_screen.dart';
import 'package:voice_to_textnote/screens/speaker_profile_screen.dart';
// SPEC-TEAM-001: 팀 관리 화면 추가
import 'package:voice_to_textnote/screens/team_list_screen.dart';
import 'package:voice_to_textnote/screens/search_screen.dart';
import 'package:voice_to_textnote/screens/team_detail_screen.dart';
// SPEC-MOBILE-001: 딥링크 서비스
import 'package:voice_to_textnote/services/deep_link_service.dart';

// 인증이 불필요한 공개 경로 목록
const _publicPaths = ['/login', '/register'];

// @MX:ANCHOR: 앱 전역 라우터 - 인증 리다이렉트 로직 포함
// @MX:REASON: goRouter는 ProviderScope 외부에서 생성되므로 ref를 직접 받아야 함
GoRouter createRouter(ProviderContainer container) {
  final router = GoRouter(
    initialLocation: '/',
    // 인증 상태 변화 감지를 위한 리프레시 리스너
    refreshListenable: _AuthStateNotifier(container),
    redirect: (context, state) {
      final authState = container.read(authStateProvider);
      final isAuthenticated = authState.isAuthenticated;
      // SPEC-GUEST-001: 게스트 모드도 홈 접근 허용
      final isGuest = authState.isGuest;
      final isLoading = authState.isLoading || authState.status == AuthStatus.initial;
      final currentPath = state.uri.path;

      // 초기화/로딩 중에는 리다이렉트 없음
      if (isLoading) return null;

      final isPublicPath = _publicPaths.contains(currentPath);

      // 미인증 + 비게스트 상태에서 보호된 경로 접근 시 로그인으로
      if (!isAuthenticated && !isGuest && !isPublicPath) return '/login';

      // 인증(정식 로그인) 상태에서 공개 경로(로그인/회원가입) 접근 시 홈으로
      // @MX:WARN: 게스트는 제외 — 게스트→회원가입 전환은 정상 플로우이므로 허용해야 함.
      // 이전 코드는 (isAuthenticated || isGuest) 조건으로 게스트의 /register 이동을 차단하여
      // "가입하기 버튼이 먹통"인 버그의 원인이 됨.
      if (isAuthenticated && !isGuest && isPublicPath) return '/';

      return null;
    },
    routes: [
      // 홈 화면 - 미팅 목록
      GoRoute(
        path: '/',
        builder: (_, __) => const HomeScreen(),
      ),
      // 로그인 화면
      GoRoute(
        path: '/login',
        builder: (_, __) => const LoginScreen(),
      ),
      // 회원가입 화면
      GoRoute(
        path: '/register',
        builder: (_, __) => const RegisterScreen(),
      ),
      // 녹음 화면
      GoRoute(
        path: '/recording',
        builder: (_, __) => const RecordingScreen(),
      ),
      // 처리 중 화면 (미팅 ID 파라미터)
      GoRoute(
        path: '/processing/:id',
        builder: (_, state) => ProcessingScreen(
          meetingId: state.pathParameters['id']!,
        ),
      ),
      // 결과 화면 (미팅 ID 파라미터)
      GoRoute(
        path: '/result/:id',
        builder: (_, state) => ResultScreen(
          meetingId: state.pathParameters['id']!,
        ),
      ),
      // 검색 화면 (SPEC-SEARCH-001)
      GoRoute(
        path: '/search',
        builder: (_, __) => const SearchScreen(),
      ),
      // 양식 관리 화면 (SPEC-TMPL-001 REQ-TMPL-007)
      GoRoute(
        path: '/templates',
        builder: (_, __) => const TemplateScreen(),
      ),
      // 사용자 사전 관리 화면
      GoRoute(
        path: '/vocabulary',
        builder: (_, __) => const VocabularyScreen(),
      ),
      // 화자 프로필 관리 화면 (SPEC-SPEAKER-001)
      GoRoute(
        path: '/speakers',
        builder: (_, state) => SpeakerProfileScreen(
          taskId: state.uri.queryParameters['taskId'],
        ),
      ),
      // 팀 목록 화면 (SPEC-TEAM-001 REQ-TEAM-006)
      GoRoute(
        path: '/teams',
        builder: (_, __) => const TeamListScreen(),
      ),
      // 팀 상세 화면 (SPEC-TEAM-001 REQ-TEAM-006)
      GoRoute(
        path: '/teams/:id',
        builder: (_, state) => TeamDetailScreen(
          teamId: state.pathParameters['id']!,
        ),
      ),
      // 설정 화면
      GoRoute(
        path: '/settings',
        builder: (_, __) => const SettingsScreen(),
      ),
    ],
  );

  // SPEC-MOBILE-001: 딥링크 서비스에 라우터 등록
  DeepLinkService.instance.setRouter(router);

  return router;
}

// 인증 상태 변화를 GoRouter에 알려주는 리스너
class _AuthStateNotifier extends ChangeNotifier {
  final ProviderContainer _container;
  ProviderSubscription<AuthState>? _subscription;

  _AuthStateNotifier(this._container) {
    _subscription = _container.listen<AuthState>(
      authStateProvider,
      (_, __) => notifyListeners(),
    );
  }

  @override
  void dispose() {
    _subscription?.close();
    super.dispose();
  }
}
