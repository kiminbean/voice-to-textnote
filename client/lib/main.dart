// 앱 진입점
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/router/app_router.dart';

void main() {
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
