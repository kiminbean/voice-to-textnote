import 'package:voice_to_textnote/services/local_stt_service.dart';
import 'package:whisper_ggml_plus/whisper_ggml_plus.dart';

class WhisperGgmlLocalSttRuntime implements LocalSttRuntime {
  const WhisperGgmlLocalSttRuntime();

  @override
  Future<bool> isAvailable() async {
    try {
      final version = await _whisper().getVersion();
      return version != null && version.trim().isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<String> runtimeInfo() async {
    try {
      return await _whisper().getVersion() ?? 'unknown';
    } catch (error) {
      return error.toString();
    }
  }

  @override
  Future<LocalSttResult> transcribe({
    required String audioFilePath,
    required String modelPath,
    required String language,
  }) async {
    final response = await _whisper().transcribe(
      transcribeRequest: TranscribeRequest(
        audio: audioFilePath,
        language: language,
        isNoTimestamps: false,
        vadMode: WhisperVadMode.auto,
      ),
      modelPath: modelPath,
    );

    final segments = response.segments ?? const <WhisperTranscribeSegment>[];
    return LocalSttResult(
      text: response.text.trim(),
      language: language,
      durationSeconds: _durationSeconds(segments),
      segments: [
        for (var i = 0; i < segments.length; i++)
          LocalSttSegment(
            id: i,
            start: segments[i].fromTs.inMilliseconds / 1000.0,
            end: segments[i].toTs.inMilliseconds / 1000.0,
            text: segments[i].text.trim(),
            confidence: 1.0,
          ),
      ],
    );
  }

  Whisper _whisper() {
    return const Whisper(model: WhisperModel.base);
  }
}

double _durationSeconds(List<WhisperTranscribeSegment> segments) {
  if (segments.isEmpty) return 0.0;
  return segments.last.toTs.inMilliseconds / 1000.0;
}
