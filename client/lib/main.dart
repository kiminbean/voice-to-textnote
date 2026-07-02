// 앱 진입점
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/firebase_config.dart';
import 'package:voice_to_textnote/config/ui_test_mode.dart';
import 'package:voice_to_textnote/l10n/app_localizations.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/providers/notification_provider.dart';
import 'package:voice_to_textnote/providers/permission_recheck_provider.dart';
import 'package:voice_to_textnote/providers/theme_mode_provider.dart';
import 'package:voice_to_textnote/router/app_router.dart';
import 'package:voice_to_textnote/services/deep_link_service.dart';

import 'package:voice_to_textnote/services/push_notification_service.dart';
import 'package:voice_to_textnote/services/shared_import_service.dart';
import 'package:voice_to_textnote/services/auth_service.dart';
import 'package:voice_to_textnote/theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Firebase 초기화 (우회 지원)
  await FirebaseConfig.initializeFirebase();

  // 백그라운드 메시지 핸들러 등록
  registerFCMBackgroundHandler();

  final uiTestMode = await UiTestMode.detect();
  if (uiTestMode) {
    final authService = AuthService();
    await Future.wait([
      authService.clearTokens(),
      authService.clearGuestSession(),
    ]);
  }

  runApp(VoiceToTextNoteApp(uiTestMode: uiTestMode));
}

class VoiceToTextNoteApp extends StatefulWidget {
  final bool uiTestMode;

  const VoiceToTextNoteApp({
    super.key,
    this.uiTestMode = false,
  });

  @override
  State<VoiceToTextNoteApp> createState() => _VoiceToTextNoteAppState();
}

class _VoiceToTextNoteAppState extends State<VoiceToTextNoteApp>
    with WidgetsBindingObserver {
  late final ProviderContainer _container;
  late final router = createRouter(_container, uiTestMode: widget.uiTestMode);
  ProviderSubscription<AuthState>? _authSubscription;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _container = ProviderContainer();
    _authSubscription = _container.listen<AuthState>(
      authStateProvider,
      (previous, next) {
        final wasSignedIn =
            previous?.isAuthenticated == true || previous?.isGuest == true;
        final isSignedIn = next.isAuthenticated || next.isGuest;
        if (!wasSignedIn && isSignedIn) {
          _container.read(notificationProvider.notifier).initialize();
        }
      },
    );
    _initializeAuthAndNotifications();
    _container.read(themeModeProvider.notifier).load();

    // SPEC-MOBILE-004 T-005: 딥링크 핸들러 연동
    DeepLinkService.instance.handleBackgroundResume();
    _checkColdStartDeepLink();
    _checkInitialNativeDeepLink();
    _checkInitialSharedImport();
  }

  Future<void> _initializeAuthAndNotifications() async {
    await _container.read(authStateProvider.notifier).checkAuth();
  }

  Future<void> _checkColdStartDeepLink() async {
    try {
      final notificationNotifier =
          _container.read(notificationProvider.notifier);
      final meetingId = await notificationNotifier.checkInitialMessage();
      if (meetingId != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            router.go('/result/$meetingId');
          }
        });
      }
    } catch (e) {
      debugPrint('딥링크 확인 실패: $e');
    }
  }

  Future<void> _checkInitialNativeDeepLink() async {
    try {
      final path =
          await DeepLinkService.instance.consumeInitialNativeDeepLink();
      if (path == null) return;

      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          router.go(path);
        }
      });
    } catch (e) {
      debugPrint('네이티브 초기 딥링크 확인 실패: $e');
    }
  }

  Future<void> _checkInitialSharedImport() async {
    try {
      final payload = await SharedImportService().consumeInitialSharedImport();
      if (payload == null || !payload.hasContent) return;

      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        final uri =
            Uri(path: '/', queryParameters: payload.toQueryParameters());
        router.go(uri.toString());
      });
    } catch (e) {
      debugPrint('공유 import 확인 실패: $e');
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // SPEC-MOBILE-005 REQ-005: 백그라운드 진입 시 녹음 상태 보존
    switch (state) {
      case AppLifecycleState.resumed:
        _container.read(notificationProvider.notifier).checkInitialMessage();
        _checkLatestSharedImport();
        // T-015: 설정 앱에서 권한 변경 후 복귀 시 UI 갱신 트리거
        _container.read(permissionRecheckProvider.notifier).triggerRecheck();
        break;
      case AppLifecycleState.inactive:
        // 포그라운드 비활성 (알림 센터 드래그 등) — 녹음은 유지됨
        debugPrint('AppLifecycleState.inactive — 녹음 유지');
        break;
      case AppLifecycleState.paused:
        // 백그라운드 진입 — audio session이 활성 상태면 녹음 계속됨
        debugPrint('AppLifecycleState.paused — 백그라운드 녹음 모드');
        break;
      case AppLifecycleState.detached:
        // 엔진 분리 (강제 종료 등) — 복구 데이터가 이미 SharedPreferences에 저장됨
        debugPrint('AppLifecycleState.detached — 복구 데이터 저장됨');
        break;
      case AppLifecycleState.hidden:
        // iOS 다중 태스크 전환 화면 — 녹음 유지
        debugPrint('AppLifecycleState.hidden — 녹음 유지');
        break;
    }
  }

  Future<void> _checkLatestSharedImport() async {
    try {
      final path = await DeepLinkService.instance.consumeLatestNativeDeepLink();
      if (path != null) {
        router.go(path);
        return;
      }

      final payload = await SharedImportService().consumeLatestSharedImport();
      if (payload == null || !payload.hasContent) return;
      final uri = Uri(path: '/', queryParameters: payload.toQueryParameters());
      router.go(uri.toString());
    } catch (e) {
      debugPrint('최근 공유 import 확인 실패: $e');
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _authSubscription?.close();
    _container.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return UncontrolledProviderScope(
      container: _container,
      child: Consumer(
        builder: (context, ref, _) {
          final themeState = ref.watch(themeModeProvider);
          return MaterialApp.router(
            title: 'Voice TextNote',
            debugShowCheckedModeBanner: false,
            theme: buildAppLightTheme(),
            darkTheme: buildAppDarkTheme(),
            themeMode: themeState.mode.toMaterial(),
            localizationsDelegates: const [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: const [
              Locale('ko'),
              Locale('en'),
            ],
            routerConfig: router,
          );
        },
      ),
    );
  }
}
