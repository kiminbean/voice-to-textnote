// SPEC-TONE-001: 음성 톤 분석 응답 데이터 모델 (REQ-TONE-012)
// @MX:SPEC: SPEC-TONE-001
// 패턴 매칭: sentiment_api.dart (fromJson + snake_case↔camelCase 매핑)
import 'package:flutter/foundation.dart';

// @MX:NOTE: 백엔드 톤 클래스 계약 - calm/excited/authoritative/hesitant/monotone/unknown
// 클라이언트 색상 매핑(toneColor)과 1:1 대응됨

/// 톤 분석 개별 세그먼트 (구간별 톤 분류 + prosody 특성)
class ToneSegment {
  final double start;
  final double end;
  final String speaker;
  final String tone;
  final double confidence;
  final Map<String, double> prosodyFeatures;

  const ToneSegment({
    required this.start,
    required this.end,
    required this.speaker,
    required this.tone,
    required this.confidence,
    required this.prosodyFeatures,
  });

  factory ToneSegment.fromJson(Map<String, dynamic> json) {
    // prosody_features: snake_case → camelCase, int/num 혼용 허용
    final prosody = <String, double>{};
    final raw = json['prosody_features'] as Map<String, dynamic>?;
    if (raw != null) {
      for (final entry in raw.entries) {
        prosody[entry.key] = (entry.value as num).toDouble();
      }
    }
    return ToneSegment(
      start: (json['start'] as num).toDouble(),
      end: (json['end'] as num).toDouble(),
      speaker: json['speaker'] as String? ?? 'UNKNOWN',
      tone: json['tone'] as String? ?? 'unknown',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      prosodyFeatures: prosody,
    );
  }

  Map<String, dynamic> toJson() => {
        'start': start,
        'end': end,
        'speaker': speaker,
        'tone': tone,
        'confidence': confidence,
        'prosody_features': prosodyFeatures,
      };

  ToneSegment copyWith({
    double? start,
    double? end,
    String? speaker,
    String? tone,
    double? confidence,
    Map<String, double>? prosodyFeatures,
  }) =>
      ToneSegment(
        start: start ?? this.start,
        end: end ?? this.end,
        speaker: speaker ?? this.speaker,
        tone: tone ?? this.tone,
        confidence: confidence ?? this.confidence,
        prosodyFeatures: prosodyFeatures ?? this.prosodyFeatures,
      );

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ToneSegment &&
          runtimeType == other.runtimeType &&
          start == other.start &&
          end == other.end &&
          speaker == other.speaker &&
          tone == other.tone &&
          confidence == other.confidence &&
          _doubleMapEquals(prosodyFeatures, other.prosodyFeatures);

  @override
  int get hashCode => Object.hash(
        start,
        end,
        speaker,
        tone,
        confidence,
        Object.hashAll(prosodyFeatures.entries),
      );
}

/// 화자별 톤 요약 (dominant_tone + 분포 + 평균 prosody)
class SpeakerTone {
  final String speaker;
  final String dominantTone;
  final Map<String, double> toneDistribution;
  final double avgPitch;
  final double avgEnergy;

  const SpeakerTone({
    required this.speaker,
    required this.dominantTone,
    required this.toneDistribution,
    required this.avgPitch,
    required this.avgEnergy,
  });

  factory SpeakerTone.fromJson(Map<String, dynamic> json) {
    // tone_distribution: 백엔드는 int 값을 줄 수 있으나 클라이언트는 double로 정규화
    final distribution = <String, double>{};
    final raw = json['tone_distribution'] as Map<String, dynamic>?;
    if (raw != null) {
      for (final entry in raw.entries) {
        distribution[entry.key] = (entry.value as num).toDouble();
      }
    }
    return SpeakerTone(
      speaker: json['speaker'] as String? ?? 'UNKNOWN',
      dominantTone: json['dominant_tone'] as String? ?? 'unknown',
      toneDistribution: distribution,
      avgPitch: (json['avg_pitch'] as num?)?.toDouble() ?? 0.0,
      avgEnergy: (json['avg_energy'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'speaker': speaker,
        'dominant_tone': dominantTone,
        'tone_distribution': toneDistribution,
        'avg_pitch': avgPitch,
        'avg_energy': avgEnergy,
      };

  SpeakerTone copyWith({
    String? speaker,
    String? dominantTone,
    Map<String, double>? toneDistribution,
    double? avgPitch,
    double? avgEnergy,
  }) =>
      SpeakerTone(
        speaker: speaker ?? this.speaker,
        dominantTone: dominantTone ?? this.dominantTone,
        toneDistribution: toneDistribution ?? this.toneDistribution,
        avgPitch: avgPitch ?? this.avgPitch,
        avgEnergy: avgEnergy ?? this.avgEnergy,
      );

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SpeakerTone &&
          runtimeType == other.runtimeType &&
          speaker == other.speaker &&
          dominantTone == other.dominantTone &&
          avgPitch == other.avgPitch &&
          avgEnergy == other.avgEnergy &&
          _doubleMapEquals(toneDistribution, other.toneDistribution);

  @override
  int get hashCode => Object.hash(
        speaker,
        dominantTone,
        avgPitch,
        avgEnergy,
        Object.hashAll(toneDistribution.entries),
      );
}

/// 톤 분석 전체 응답 (task_id 기준 + segments + speakers + overall)
class ToneResponse {
  final String taskId;
  final String status;
  final List<ToneSegment> segments;
  final List<SpeakerTone> speakers;
  final String overallTone;
  final String? errorMessage;

  const ToneResponse({
    required this.taskId,
    required this.status,
    required this.segments,
    required this.speakers,
    required this.overallTone,
    this.errorMessage,
  });

  factory ToneResponse.fromJson(Map<String, dynamic> json) {
    final segmentsRaw = json['segments'] as List? ?? [];
    final speakersRaw = json['speakers'] as List? ?? [];
    return ToneResponse(
      taskId: json['task_id'] as String? ?? '',
      status: json['status'] as String? ?? 'unknown',
      segments: segmentsRaw
          .map((e) => ToneSegment.fromJson(e as Map<String, dynamic>))
          .toList(),
      speakers: speakersRaw
          .map((e) => SpeakerTone.fromJson(e as Map<String, dynamic>))
          .toList(),
      overallTone: json['overall_tone'] as String? ?? 'unknown',
      errorMessage: json['error_message'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'task_id': taskId,
        'status': status,
        'segments': segments.map((e) => e.toJson()).toList(),
        'speakers': speakers.map((e) => e.toJson()).toList(),
        'overall_tone': overallTone,
        if (errorMessage != null) 'error_message': errorMessage,
      };

  ToneResponse copyWith({
    String? taskId,
    String? status,
    List<ToneSegment>? segments,
    List<SpeakerTone>? speakers,
    String? overallTone,
    String? errorMessage,
  }) =>
      ToneResponse(
        taskId: taskId ?? this.taskId,
        status: status ?? this.status,
        segments: segments ?? this.segments,
        speakers: speakers ?? this.speakers,
        overallTone: overallTone ?? this.overallTone,
        errorMessage: errorMessage ?? this.errorMessage,
      );

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ToneResponse &&
          runtimeType == other.runtimeType &&
          taskId == other.taskId &&
          status == other.status &&
          overallTone == other.overallTone &&
          errorMessage == other.errorMessage &&
          listEquals(segments, other.segments) &&
          listEquals(speakers, other.speakers);

  @override
  int get hashCode =>
      Object.hash(taskId, status, overallTone, errorMessage, segments, speakers);
}

// @MX:NOTE: Map<String,double> 값 비교 헬퍼 - foundation의 mapEquals 미지원 대응
bool _doubleMapEquals(Map<String, double> a, Map<String, double> b) {
  if (identical(a, b)) return true;
  if (a.length != b.length) return false;
  for (final key in a.keys) {
    if (a[key] != b[key]) return false;
  }
  return true;
}
