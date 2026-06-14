import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/local_stt_runtime_whisper.dart';
import 'package:voice_to_textnote/services/local_stt_service.dart';
import 'package:voice_to_textnote/services/model_manager.dart';

final localSttServiceProvider = Provider<LocalSttService>((ref) {
  return LocalSttService(
    ref.watch(modelManagerProvider),
    runtime: const WhisperGgmlLocalSttRuntime(),
  );
});
