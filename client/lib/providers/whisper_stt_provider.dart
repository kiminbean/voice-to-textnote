import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/platform_stt_service.dart';

/// WhisperSttService 인스턴스 제공
final whisperSttServiceProvider = Provider<PlatformSttService>((ref) {
  final service = WhisperSttServiceImpl();
  ref.onDispose(() => service.dispose());
  return service;
});
