// SPEC-MOBILE-002: 로컬 STT 서비스

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

  factory LocalSttResult.fromMap(Map<String, Object?> map) {
    final segments = <LocalSttSegment>[];
    final rawSegments = map['segments'];
    if (rawSegments is List) {
      for (final rawSegment in rawSegments) {
        if (rawSegment is Map) {
          segments
              .add(LocalSttSegment.fromMap(rawSegment.cast<String, Object?>()));
        }
      }
    }

    return LocalSttResult(
      text: (map['text'] as String?)?.trim() ?? '',
      segments: segments,
      language: (map['language'] as String?) ?? 'ko',
      durationSeconds: _asDouble(map['durationSeconds']),
    );
  }
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

  factory LocalSttSegment.fromMap(Map<String, Object?> map) {
    return LocalSttSegment(
      id: _asInt(map['id']),
      start: _asDouble(map['start']),
      end: _asDouble(map['end']),
      text: (map['text'] as String?)?.trim() ?? '',
      confidence: _asDouble(map['confidence'], fallback: 1.0),
    );
  }
}

class LocalSttService {
  final LocalSttModelSource _modelManager;
  final LocalSttRuntime _runtime;

  LocalSttService(
    this._modelManager, {
    required LocalSttRuntime runtime,
  }) : _runtime = runtime;

  Future<bool> isAvailable() async {
    if (!await _modelManager.isModelReady()) {
      return false;
    }
    return isRuntimeAvailable();
  }

  Future<bool> isRuntimeAvailable() async {
    return _runtime.isAvailable();
  }

  Future<String> runtimeInfo() async {
    return _runtime.runtimeInfo();
  }

  Future<LocalSttResult> transcribe(String audioFilePath) async {
    if (!await _modelManager.isModelReady()) {
      throw StateError('오프라인 STT 모델이 준비되지 않았습니다');
    }
    if (!await isRuntimeAvailable()) {
      final info = await runtimeInfo();
      throw StateError('오프라인 STT 런타임이 준비되지 않았습니다: $info');
    }

    final modelPath = await _modelManager.getModelPath();
    if (modelPath == null) {
      throw StateError('오프라인 STT 모델 경로를 찾을 수 없습니다');
    }

    return _runtime.transcribe(
      audioFilePath: audioFilePath,
      modelPath: modelPath,
      language: 'ko',
    );
  }

  Future<String> get modelInfo async {
    if (!await _modelManager.isModelReady()) return '모델 미설치';
    if (!await isRuntimeAvailable()) {
      return '런타임 미연결 (${await runtimeInfo()})';
    }
    final path = await _modelManager.getModelPath();
    return 'whisper-base ($path)';
  }
}

abstract interface class LocalSttModelSource {
  Future<bool> isModelReady();

  Future<String?> getModelPath();
}

abstract interface class LocalSttRuntime {
  Future<bool> isAvailable();

  Future<String> runtimeInfo();

  Future<LocalSttResult> transcribe({
    required String audioFilePath,
    required String modelPath,
    required String language,
  });
}

double _asDouble(Object? value, {double fallback = 0.0}) {
  if (value is double) return value;
  if (value is int) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? fallback;
  return fallback;
}

int _asInt(Object? value, {int fallback = 0}) {
  if (value is int) return value;
  if (value is double) return value.toInt();
  if (value is String) return int.tryParse(value) ?? fallback;
  return fallback;
}
