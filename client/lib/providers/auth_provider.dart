// 인증 상태 관리 프로바이더
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';
import 'package:voice_to_textnote/models/auth_user.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/services/auth_api.dart';
import 'package:voice_to_textnote/services/auth_service.dart';

// 인증 상태 sealed class 대신 enum + 데이터 클래스 사용 (freezed 미사용 프로젝트)
enum AuthStatus { initial, loading, authenticated, unauthenticated, guest }

class AuthState {
  final AuthStatus status;
  final AuthUser? user;
  final String? errorMessage;

  const AuthState({
    required this.status,
    this.user,
    this.errorMessage,
  });

  const AuthState.initial()
      : status = AuthStatus.initial,
        user = null,
        errorMessage = null;
  const AuthState.loading()
      : status = AuthStatus.loading,
        user = null,
        errorMessage = null;
  const AuthState.authenticated(AuthUser u)
      : status = AuthStatus.authenticated,
        user = u,
        errorMessage = null;
  const AuthState.unauthenticated([String? msg])
      : status = AuthStatus.unauthenticated,
        user = null,
        errorMessage = msg;
  // SPEC-GUEST-001: 게스트 상태 - authenticated와 동일하게 홈 접근 허용
  const AuthState.guest()
      : status = AuthStatus.guest,
        user = null,
        errorMessage = null;

  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isLoading => status == AuthStatus.loading;
  // SPEC-GUEST-001: 게스트 여부 - 라우터와 홈 배너에서 사용
  bool get isGuest => status == AuthStatus.guest;
}

const googleIosClientId = String.fromEnvironment(
  'GOOGLE_IOS_CLIENT_ID',
  defaultValue:
      '546416114080-456ie1r6jeolaitjfheaflsko521tqt0.apps.googleusercontent.com',
);

const googleMacosClientId = String.fromEnvironment(
  'GOOGLE_MACOS_CLIENT_ID',
  defaultValue:
      '546416114080-qvu4stec0b25hl4bksrsl77rgb9bk7dg.apps.googleusercontent.com',
);

const googleServerClientId = String.fromEnvironment(
  'GOOGLE_SERVER_CLIENT_ID',
  defaultValue:
      '546416114080-rqu4hpn5rdes9dein5r2squenh17q646.apps.googleusercontent.com',
);

String? googleClientIdForPlatform({
  required bool isIOS,
  bool isMacOS = false,
}) {
  if (isIOS) return googleIosClientId;
  if (isMacOS) return googleMacosClientId;
  return null;
}

bool isGoogleSignInConfiguredForPlatform({
  required bool isIOS,
  bool isMacOS = false,
}) {
  final clientId = googleClientIdForPlatform(isIOS: isIOS, isMacOS: isMacOS);
  return googleServerClientId.isNotEmpty &&
      (clientId == null || clientId.isNotEmpty);
}

bool shouldClearGoogleSelectionBeforeSignIn({
  required bool isIOS,
}) {
  return !isIOS;
}

String socialLoginErrorMessage(Exception e, String provider) {
  final msg = e.toString();
  final lowerMsg = msg.toLowerCase();
  final platformCode = e is PlatformException ? e.code.toLowerCase() : '';
  final platformMessage =
      e is PlatformException ? (e.message ?? '').toLowerCase() : '';

  final isProviderConfigurationError = provider == 'Google' &&
      (platformCode.contains('developer_error') ||
          platformCode == '10' ||
          platformMessage.contains('developer_error') ||
          platformMessage.contains('apiexception: 10') ||
          platformMessage.contains('api exception: 10') ||
          platformMessage.contains('oauth') ||
          platformMessage.contains('not registered') ||
          lowerMsg.contains('developer_error') ||
          lowerMsg.contains('apiexception: 10') ||
          lowerMsg.contains('api exception: 10') ||
          lowerMsg.contains('oauth') ||
          lowerMsg.contains('not registered') ||
          lowerMsg.contains('server client id'));
  if (isProviderConfigurationError) {
    return 'Google 로그인 설정에 문제가 있습니다. 앱 서명과 OAuth 클라이언트 설정을 확인해주세요.';
  }
  if (msg.contains('401') || msg.contains('Unauthorized')) {
    return '$provider 인증에 실패했습니다. 잠시 후 다시 시도해주세요.';
  }
  if (msg.contains('SocketException') || msg.contains('connection')) {
    return '서버에 연결할 수 없습니다. 네트워크를 확인해주세요.';
  }
  return '$provider 로그인 중 오류가 발생했습니다. 다시 시도해주세요.';
}

// @MX:ANCHOR: 앱 전역 인증 상태를 관리하는 핵심 Notifier
// @MX:REASON: goRouter redirect, dioProvider interceptor 양쪽에서 참조
class AuthNotifier extends StateNotifier<AuthState> {
  final AuthApi _authApi;
  final AuthService _authService;
  // Ref는 선택적: 신원 전환 시 회의 캐시 정리에만 사용한다.
  // 미주입(일부 단위 테스트) 시 캐시 정리를 건너뛴다.
  final Ref? _ref;

  AuthNotifier(this._authApi, this._authService, [this._ref])
      : super(const AuthState.initial());

  // 신원 전환 시 이전 사용자/게스트의 로컬 회의 목록 캐시를 비운다.
  // 실패해도 인증 흐름을 막지 않는다 (best-effort).
  Future<void> _clearMeetingCache() async {
    final ref = _ref;
    if (ref == null) return;
    try {
      await ref.read(meetingListProvider.notifier).clearLocalCache();
      ref.invalidate(meetingListProvider);
    } catch (_) {}
  }

  // 앱 시작 시 저장된 토큰으로 인증 상태 복원
  // SPEC-GUEST-001: 게스트 토큰이 있으면 게스트 상태로 복원
  Future<void> checkAuth() async {
    state = const AuthState.loading();
    try {
      // 실제 로그인 토큰을 게스트 세션보다 우선 복원한다.
      // 게스트 토큰이 남아 있으면 사용자 전용 API(/speakers 등)가 401을 반환한다.
      final hasTokens = await _authService.hasTokens();
      if (hasTokens) {
        // 만료 여부 확인 후 갱신 시도
        final isExpired = await _authService.isAccessTokenExpired();
        if (isExpired) {
          final refreshed = await _tryRefresh();
          if (!refreshed) {
            state = const AuthState.unauthenticated();
            return;
          }
        }

        // 사용자 정보 조회
        final accessToken = await _authService.getAccessToken();
        if (accessToken == null) {
          state = const AuthState.unauthenticated();
          return;
        }

        final user = await _authApi.getMe(accessToken);
        state = AuthState.authenticated(user);
        return;
      }

      // 로그인 토큰이 없을 때만 게스트 세션을 복원한다.
      final isGuest = await _authService.isGuestMode();
      if (isGuest) {
        state = const AuthState.guest();
        return;
      }

      state = const AuthState.unauthenticated();
    } catch (_) {
      await _authService.clearTokens();
      state = const AuthState.unauthenticated();
    }
  }

  // 토큰을 저장하고, 직전 게스트 세션으로 녹음한 회의를 계정으로 인계한다.
  // saveTokens가 게스트 세션을 삭제하므로 반드시 그 전에 게스트 토큰을 읽어둔다.
  Future<void> _persistTokensAndClaimGuest(
    String accessToken,
    String refreshToken,
  ) async {
    final guestToken = await _authService.getGuestToken();
    await _authService.saveTokens(accessToken, refreshToken);
    if (guestToken != null && guestToken.isNotEmpty) {
      try {
        // 인계 실패는 로그인 자체를 막지 않는다 (best-effort)
        await _authApi.claimGuestMeetings(guestToken);
      } catch (_) {}
    }
    // 로그인으로 신원이 바뀌었으므로 이전 캐시를 비우고 서버 기준으로 다시 동기화한다.
    await _clearMeetingCache();
  }

  // 로그인
  Future<void> login(String email, String password) async {
    state = const AuthState.loading();
    try {
      final response = await _authApi.login(email: email, password: password);
      await _persistTokensAndClaimGuest(
          response.accessToken, response.refreshToken);
      // 토큰으로 사용자 정보 조회
      final user = await _authApi.getMe(response.accessToken);
      state = AuthState.authenticated(user);
    } on Exception catch (e) {
      state = AuthState.unauthenticated(_parseError(e));
    }
  }

  // 회원가입 (성공 시 자동 로그인)
  Future<void> register(
      String email, String password, String displayName) async {
    state = const AuthState.loading();
    try {
      final response = await _authApi.register(
        email: email,
        password: password,
        displayName: displayName,
      );
      await _persistTokensAndClaimGuest(
          response.accessToken, response.refreshToken);
      // 토큰으로 사용자 정보 조회
      final user = await _authApi.getMe(response.accessToken);
      state = AuthState.authenticated(user);
    } on Exception catch (e) {
      state = AuthState.unauthenticated(_parseError(e));
    }
  }

  // 로그아웃 (일반 + 게스트 공통)
  // SPEC-GUEST-001: 게스트 세션 데이터도 함께 삭제
  Future<void> logout() async {
    try {
      final accessToken = await _authService.getAccessToken();
      final refreshToken = await _authService.getRefreshToken();
      if (accessToken != null && refreshToken != null) {
        await _authApi.logout(
          accessToken: accessToken,
          refreshToken: refreshToken,
        );
      }
    } catch (_) {
      // 서버 오류 무시하고 로컬 토큰 삭제
    } finally {
      // 일반 토큰과 게스트 세션 모두 삭제
      await Future.wait([
        _authService.clearTokens(),
        _authService.clearGuestSession(),
      ]);
      // 신원 종료: 이전 사용자의 회의가 다음 신원 목록에 남지 않도록 캐시 정리
      await _clearMeetingCache();
      state = const AuthState.unauthenticated();
    }
  }

  // 게스트로 시작 (SPEC-GUEST-001)
  // 서버에서 게스트 세션 생성 후 로컬 저장
  Future<void> startAsGuest() async {
    state = const AuthState.loading();
    try {
      final data = await _authApi.createGuestSession();
      final guestToken = data['guest_token'] as String;
      final sessionId = data['guest_session_id'] as String;
      await _authService.saveGuestToken(guestToken, sessionId);
      // 게스트로 신원이 바뀌었으므로 이전(로그인 사용자 등)의 회의 캐시를 비운다.
      await _clearMeetingCache();
      state = const AuthState.guest();
    } on Exception catch (e) {
      state = AuthState.unauthenticated(_parseError(e));
    }
  }

  // 테스트 전용: 게스트 상태로 직접 설정
  // @visibleForTesting
  void setGuestStateForTest() {
    state = const AuthState.guest();
  }

  // 테스트 전용: 인증 상태로 직접 설정
  // @visibleForTesting
  void setAuthenticatedStateForTest(AuthUser user) {
    state = AuthState.authenticated(user);
  }

  // Google 소셜 로그인 (REQ-OAUTH-001)
  Future<void> loginWithGoogle() async {
    state = const AuthState.loading();
    try {
      if (!isGoogleSignInConfiguredForPlatform(isIOS: Platform.isIOS)) {
        state = const AuthState.unauthenticated(
          'Google 로그인 설정이 완료되지 않았습니다. OAuth 클라이언트 설정이 필요합니다.',
        );
        return;
      }

      final clientId = googleClientIdForPlatform(
        isIOS: Platform.isIOS,
        isMacOS: Platform.isMacOS,
      );
      final googleSignIn = GoogleSignIn(
        clientId: clientId,
        serverClientId: googleServerClientId,
      );
      if (shouldClearGoogleSelectionBeforeSignIn(isIOS: Platform.isIOS)) {
        await googleSignIn.signOut();
      }
      final googleAccount = await googleSignIn.signIn();
      if (googleAccount == null) {
        state = const AuthState.unauthenticated();
        return;
      }

      final googleAuth = await googleAccount.authentication;
      final idToken = googleAuth.idToken;
      if (idToken == null) {
        state = const AuthState.unauthenticated('Google 인증에 실패했습니다.');
        return;
      }

      final response = await _authApi.loginWithGoogle(idToken: idToken);
      await _persistTokensAndClaimGuest(
          response.accessToken, response.refreshToken);
      final user = await _authApi.getMe(response.accessToken);
      state = AuthState.authenticated(user);
    } on Exception catch (e) {
      state = AuthState.unauthenticated(_parseSocialLoginError(e, 'Google'));
    }
  }

  // Apple 소셜 로그인 (REQ-OAUTH-001)
  Future<void> loginWithApple() async {
    state = const AuthState.loading();
    try {
      final credential = await SignInWithApple.getAppleIDCredential(
        scopes: [
          AppleIDAuthorizationScopes.email,
          AppleIDAuthorizationScopes.fullName,
        ],
      );

      final idToken = credential.identityToken;
      if (idToken == null) {
        state = const AuthState.unauthenticated('Apple 인증에 실패했습니다.');
        return;
      }

      final displayName = [
        credential.givenName,
        credential.familyName,
      ].where((n) => n != null && n.isNotEmpty).join(' ');

      final response = await _authApi.loginWithApple(
        idToken: idToken,
        displayName: displayName.isEmpty ? null : displayName,
      );
      await _persistTokensAndClaimGuest(
          response.accessToken, response.refreshToken);
      final user = await _authApi.getMe(response.accessToken);
      state = AuthState.authenticated(user);
    } on Exception catch (e) {
      state = AuthState.unauthenticated(_parseSocialLoginError(e, 'Apple'));
    }
  }

  // 토큰 갱신 시도 (내부용)
  Future<bool> _tryRefresh() async {
    try {
      final refreshToken = await _authService.getRefreshToken();
      if (refreshToken == null) return false;
      final response = await _authApi.refresh(refreshToken);
      await _authService.saveTokens(
          response.accessToken, response.refreshToken);
      return true;
    } catch (_) {
      await _authService.clearTokens();
      return false;
    }
  }

  // 에러 메시지 파싱
  String _parseError(Exception e) {
    final msg = e.toString();
    if (msg.contains('401') || msg.contains('Unauthorized')) {
      return '이메일 또는 비밀번호가 올바르지 않습니다.';
    }
    if (msg.contains('409') || msg.contains('Conflict')) {
      return '이미 사용 중인 이메일입니다.';
    }
    if (msg.contains('SocketException') || msg.contains('connection')) {
      return '서버에 연결할 수 없습니다. 네트워크를 확인해주세요.';
    }
    return '오류가 발생했습니다. 다시 시도해주세요.';
  }

  String _parseSocialLoginError(Exception e, String provider) {
    return socialLoginErrorMessage(e, provider);
  }
}

// 인증 상태 프로바이더
final authStateProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(
    ref.watch(authApiProvider),
    ref.watch(authServiceProvider),
    ref,
  );
});

// 인증 여부 파생 프로바이더
final isAuthenticatedProvider = Provider<bool>((ref) {
  return ref.watch(authStateProvider).isAuthenticated;
});

// 현재 사용자 파생 프로바이더
final currentUserProvider = Provider<AuthUser?>((ref) {
  return ref.watch(authStateProvider).user;
});
