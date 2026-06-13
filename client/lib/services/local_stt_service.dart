// SPEC-MOBILE-002: 로컬 STT 서비스 (추상 + stub 구현)
//
// whisper.cpp 네이티브 바인딩은 향후 FFI/MethodChannel로 구현 예정.
// 현재는 stub으로 NotImplementedError를 반환하여 하이브리드 파이프라인에서
// 우아한 fallback을 제공한다.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/model_manager.dart';

final localSttServiceProvider = Provider<LocalSttService>((ref) {
  return LocalSttService(ref.watch(modelManagerProvider));
});

class LocalSttResult {
  final String text;
  final List<LocalSttSegment> segments;
  final String language;
  final double durationSeconds;

  const LocalSttResult({
    required this.text,
    required this.segments,
    required this.language,
    required this.durationSeconds,
  });
}

class LocalSttSegment {
  final int id;
  final double start;
  final double end;
  final String text;
  final double confidence;

  const LocalSttSegment({
    required this.id,
    required this.start,
    required this.end,
    required this.text,
    required this.confidence,
  });
}

class LocalSttService {
  final SttModelManager _modelManager;

  LocalSttService(this._modelManager);

  Future<bool> isAvailable() async {
    return _modelManager.isModelReady();
  }

  Future<LocalSttResult> transcribe(String audioFilePath) async {
    if (!await isAvailable()) {
      throw StateError('오프라인 STT 모델이 준비되지 않았습니다');
    }

    // Stub: whisper.cpp 네이티브 바인딩 구현 전까지 NotImplementedError
    throw UnimplementedError(
      'whisper.cpp 네이티브 바인딩이 아직 구현되지 않았습니다. '
      '향후 FFI 또는 MethodChannel로 구현 예정입니다.',
    );
  }

  Future<String> get modelInfo async {
    final ready = await isAvailable();
    if (!ready) return '모델 미설치';
    final path = await _modelManager.getModelPath();
    return 'whisper-base ($path)';
  }
}
