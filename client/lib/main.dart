// 앱 진입점
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/firebase_config.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/providers/notification_provider.dart';
import 'package:voice_to_textnote/providers/permission_recheck_provider.dart';
import 'package:voice_to_textnote/router/app_router.dart';
import 'package:voice_to_textnote/services/deep_link_service.dart';

import 'package:voice_to_textnote/services/push_notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Firebase 초기화 (우회 지원)
  await FirebaseConfig.initializeFirebase();

  // 백그라운드 메시지 핸들러 등록
  registerFCMBackgroundHandler();

  runApp(const VoiceToTextNoteApp());
}

class VoiceToTextNoteApp extends StatefulWidget {
  const VoiceToTextNoteApp({super.key});

  @override
  State<VoiceToTextNoteApp> createState() => _VoiceToTextNoteAppState();
}

class _VoiceToTextNoteAppState extends State<VoiceToTextNoteApp> with WidgetsBindingObserver {
  late final ProviderContainer _container;
  late final router = createRouter(_container);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _container = ProviderContainer();
    _container.read(authStateProvider.notifier).checkAuth();
    _container.read(notificationProvider.notifier).initialize();

    // SPEC-MOBILE-004 T-005: 딥링크 핸들러 연동
    DeepLinkService.instance.handleBackgroundResume();
    _checkColdStartDeepLink();
  }

  Future<void> _checkColdStartDeepLink() async {
    try {
      final notificationNotifier = _container.read(notificationProvider.notifier);
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

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _container.read(notificationProvider.notifier).checkInitialMessage();
      // T-015: 설정 앱에서 권한 변경 후 복귀 시 UI 갱신 트리거
      _container.read(permissionRecheckProvider.notifier).triggerRecheck();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _container.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return UncontrolledProviderScope(
      container: _container,
      child: MaterialApp.router(
        title: 'Voice to TextNote',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
          useMaterial3: true,
        ),
        routerConfig: router,
      ),
    );
  }
}
