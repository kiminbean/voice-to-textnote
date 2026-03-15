// 앱 진입점
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/router/app_router.dart';

void main() {
  runApp(
    const ProviderScope(
      child: VoiceToTextNoteApp(),
    ),
  );
}

class VoiceToTextNoteApp extends ConsumerWidget {
  const VoiceToTextNoteApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'Voice to TextNote',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      routerConfig: goRouter,
    );
  }
}
