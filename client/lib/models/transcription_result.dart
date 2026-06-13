// STT 전사 결과 모델 (온라인/오프라인 통합)
// @MX:NOTE: offline=true이면 로컬 whisper-base 결과, false면 백엔드 whisper-large-v3 결과

/// 전사 세그먼트
class TranscriptionSegment {
  /// 세그먼트 시작 시간
  final Duration startTime;

  /// 세그먼트 종료 시간
  final Duration endTime;

  /// 전사 텍스트
  final String text;

  /// 화자 ID (선택)
  final String? speaker;

  const TranscriptionSegment({
    required this.startTime,
    required this.endTime,
    required this.text,
    this.speaker,
  });

  /// 지정된 필드만 업데이트한 복사본 반환
  TranscriptionSegment copyWith({
    Duration? startTime,
    Duration? endTime,
    String? text,
    String? speaker,
  }) {
    return TranscriptionSegment(
      startTime: startTime ?? this.startTime,
      endTime: endTime ?? this.endTime,
      text: text ?? this.text,
      speaker: speaker ?? this.speaker,
    );
  }

  /// JSON에서 객체 생성
  factory TranscriptionSegment.fromJson(Map<String, dynamic> json) {
    return TranscriptionSegment(
      startTime: Duration(milliseconds: json['start_time'] as int),
      endTime: Duration(milliseconds: json['end_time'] as int),
      text: json['text'] as String,
      speaker: json['speaker'] as String?,
    );
  }

  /// 객체를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'start_time': startTime.inMilliseconds,
      'end_time': endTime.inMilliseconds,
      'text': text,
      'speaker': speaker,
    };
  }
}

/// STT 전사 결과 (온라인/오프라인 통합)
class TranscriptionResult {
  /// 전체 전사 텍스트
  final String text;

  /// 전사 세그먼트 리스트
  final List<TranscriptionSegment> segments;

  /// 언어 코드
  final String language;

  /// 오프라인 STT 결과 여부
  /// true = 오프라인 STT 결과 (whisper-base-coreml)
  /// false = 온라인 STT 결과 (whisper-large-v3-mlx)
  final bool offline;

  /// 생성 시각
  final DateTime createdAt;

  /// 처리 시간 (선택)
  final Duration? processingDuration;

  /// STT 엔진 정보
  /// 오프라인: "whisper-base-coreml"
  /// 온라인: "whisper-large-v3-mlx"
  final String? engineInfo;

  const TranscriptionResult({
    required this.text,
    required this.segments,
    required this.language,
    required this.offline,
    required this.createdAt,
    this.processingDuration,
    this.engineInfo,
  });

  /// 오프라인 전사 결과 생성
  factory TranscriptionResult.offline({
    required String text,
    required List<TranscriptionSegment> segments,
    required String language,
    DateTime? createdAt,
    Duration? processingDuration,
  }) {
    return TranscriptionResult(
      text: text,
      segments: segments,
      language: language,
      offline: true,
      createdAt: createdAt ?? DateTime.now(),
      processingDuration: processingDuration,
      engineInfo: 'whisper-base-coreml',
    );
  }

  /// 온라인 전사 결과 생성
  factory TranscriptionResult.online({
    required String text,
    required List<TranscriptionSegment> segments,
    required String language,
    DateTime? createdAt,
    Duration? processingDuration,
  }) {
    return TranscriptionResult(
      text: text,
      segments: segments,
      language: language,
      offline: false,
      createdAt: createdAt ?? DateTime.now(),
      processingDuration: processingDuration,
      engineInfo: 'whisper-large-v3-mlx',
    );
  }

  /// 지정된 필드만 업데이트한 복사본 반환
  TranscriptionResult copyWith({
    String? text,
    List<TranscriptionSegment>? segments,
    String? language,
    bool? offline,
    DateTime? createdAt,
    Duration? processingDuration,
    String? engineInfo,
  }) {
    return TranscriptionResult(
      text: text ?? this.text,
      segments: segments ?? this.segments,
      language: language ?? this.language,
      offline: offline ?? this.offline,
      createdAt: createdAt ?? this.createdAt,
      processingDuration: processingDuration ?? this.processingDuration,
      engineInfo: engineInfo ?? this.engineInfo,
    );
  }

  /// JSON에서 객체 생성
  factory TranscriptionResult.fromJson(Map<String, dynamic> json) {
    return TranscriptionResult(
      text: json['text'] as String,
      segments: (json['segments'] as List)
          .map((item) =>
              TranscriptionSegment.fromJson(item as Map<String, dynamic>))
          .toList(),
      language: json['language'] as String,
      offline: json['offline'] as bool,
      createdAt: DateTime.parse(json['created_at'] as String),
      processingDuration: json['processing_duration'] != null
          ? Duration(milliseconds: json['processing_duration'] as int)
          : null,
      engineInfo: json['engine_info'] as String?,
    );
  }

  /// 객체를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'text': text,
      'segments': segments.map((s) => s.toJson()).toList(),
      'language': language,
      'offline': offline,
      'created_at': createdAt.toUtc().toIso8601String(),
      'processing_duration': processingDuration?.inMilliseconds,
      'engine_info': engineInfo,
    };
  }
}
