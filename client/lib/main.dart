// 앱 진입점
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/firebase_config.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/router/app_router.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Firebase 초기화 (우회 지원)
  await FirebaseConfig.initializeFirebase();

  runApp(const ProviderScope(child: VoiceToTextNoteApp()));
}

class VoiceToTextNoteApp extends StatefulWidget {
  const VoiceToTextNoteApp({super.key});

  @override
  State<VoiceToTextNoteApp> createState() => _VoiceToTextNoteAppState();
}

class _VoiceToTextNoteAppState extends State<VoiceToTextNoteApp> {
  // ProviderContainer를 직접 관리하여 GoRouter에 전달
  late final ProviderContainer _container;
  late final router = createRouter(_container);

  @override
  void initState() {
    super.initState();
    // StatefulWidget은 ProviderScope 내부이므로 ProviderScope의 container를 가져올 수 없음
    // UncontrolledProviderScope 패턴을 사용하여 해결
    _container = ProviderContainer();
    // 앱 시작 시 저장된 토큰으로 인증 상태 복원
    _container.read(authStateProvider.notifier).checkAuth();
    // 앱 시작 시 콜드 스타트 딥링크 확인
    _checkDeepLink();
  }

  /// 콜드 스타트 딥링크 확인 (앱 종료 상태에서 알림 탭)
  Future<void> _checkDeepLink() async {
    try {
      final notificationNotifier = _container.read(notificationProvider.notifier);
      final meetingId = await notificationNotifier.checkInitialMessage();
      if (meetingId != null) {
        // 결과 화면으로 이동
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
  void dispose() {
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
