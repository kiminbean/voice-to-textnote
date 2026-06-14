import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

final sentimentApiProvider = Provider<SentimentApi>((ref) {
  final dio = ref.watch(dioProvider);
  return SentimentApi(dio);
});

class SentimentSegment {
  final double start;
  final double end;
  final String speaker;
  final String text;
  final String sentiment;
  final String emotion;
  final double confidence;

  const SentimentSegment({
    required this.start,
    required this.end,
    required this.speaker,
    required this.text,
    required this.sentiment,
    required this.emotion,
    required this.confidence,
  });

  factory SentimentSegment.fromJson(Map<String, dynamic> json) =>
      SentimentSegment(
        start: (json['start'] as num).toDouble(),
        end: (json['end'] as num).toDouble(),
        speaker: json['speaker'] as String,
        text: json['text'] as String? ?? '',
        sentiment: json['sentiment'] as String? ?? 'neutral',
        emotion: json['emotion'] as String? ?? 'neutral',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0.5,
      );
}

// SPEC-SENTIMENT-001: 백엔드 SpeakerSentiment precomputed 데이터 모델 (REQ-SEN-008)
class SpeakerSentiment {
  final String speaker;
  final int totalSegments;
  final double positiveRatio;
  final double neutralRatio;
  final double negativeRatio;
  final String dominantEmotion;
  final Map<String, int> emotionDistribution;

  const SpeakerSentiment({
    required this.speaker,
    required this.totalSegments,
    required this.positiveRatio,
    required this.neutralRatio,
    required this.negativeRatio,
    required this.dominantEmotion,
    required this.emotionDistribution,
  });

  factory SpeakerSentiment.fromJson(Map<String, dynamic> json) {
    final distribution = <String, int>{};
    final raw = json['emotion_distribution'] as Map<String, dynamic>?;
    if (raw != null) {
      for (final entry in raw.entries) {
        distribution[entry.key] = (entry.value as num).toInt();
      }
    }
    return SpeakerSentiment(
      speaker: json['speaker'] as String? ?? '알 수 없음',
      totalSegments: (json['total_segments'] as num?)?.toInt() ?? 0,
      positiveRatio: (json['positive_ratio'] as num?)?.toDouble() ?? 0.0,
      neutralRatio: (json['neutral_ratio'] as num?)?.toDouble() ?? 0.0,
      negativeRatio: (json['negative_ratio'] as num?)?.toDouble() ?? 0.0,
      dominantEmotion: json['dominant_emotion'] as String? ?? 'neutral',
      emotionDistribution: distribution,
    );
  }
}

// SPEC-SENTIMENT-001: 감정 변화 타임라인 항목 (REQ-SEN-009)
class EmotionTimelineEntry {
  final double time;
  final String sentiment;
  final String emotion;
  final String speaker;

  const EmotionTimelineEntry({
    required this.time,
    required this.sentiment,
    required this.emotion,
    required this.speaker,
  });

  factory EmotionTimelineEntry.fromJson(Map<String, dynamic> json) =>
      EmotionTimelineEntry(
        time: (json['time'] as num?)?.toDouble() ?? 0.0,
        sentiment: json['sentiment'] as String? ?? 'neutral',
        emotion: json['emotion'] as String? ?? 'neutral',
        speaker: json['speaker'] as String? ?? '알 수 없음',
      );
}

// SPEC-SENTIMENT-001: 감정 분석 전체 응답 (REQ-SEN-011, REQ-SEN-013)
// 기존 SentimentResponse 스키마와 의미 일치 유지
class SentimentFullResponse {
  final String taskId;
  final String status;
  final String minutesTaskId;
  final String overallSentiment;
  final String overallEmotion;
  final List<SentimentSegment> segments;
  final List<SpeakerSentiment> speakers;
  final List<EmotionTimelineEntry> emotionalTimeline;
  final double? generationTimeSeconds;
  final String? errorMessage;

  const SentimentFullResponse({
    required this.taskId,
    required this.status,
    required this.minutesTaskId,
    required this.overallSentiment,
    required this.overallEmotion,
    required this.segments,
    required this.speakers,
    required this.emotionalTimeline,
    this.generationTimeSeconds,
    this.errorMessage,
  });

  factory SentimentFullResponse.fromJson(Map<String, dynamic> json) {
    final segmentsRaw = json['segments'] as List? ?? [];
    final speakersRaw = json['speakers'] as List? ?? [];
    final timelineRaw = json['emotional_timeline'] as List? ?? [];

    return SentimentFullResponse(
      taskId: json['task_id'] as String? ?? '',
      status: json['status'] as String? ?? 'unknown',
      minutesTaskId: json['minutes_task_id'] as String? ?? '',
      overallSentiment: json['overall_sentiment'] as String? ?? 'neutral',
      overallEmotion: json['overall_emotion'] as String? ?? 'neutral',
      segments: segmentsRaw
          .map((e) => SentimentSegment.fromJson(e as Map<String, dynamic>))
          .toList(),
      speakers: speakersRaw
          .map((e) => SpeakerSentiment.fromJson(e as Map<String, dynamic>))
          .toList(),
      emotionalTimeline: timelineRaw
          .map((e) => EmotionTimelineEntry.fromJson(e as Map<String, dynamic>))
          .toList(),
      generationTimeSeconds:
          (json['generation_time_seconds'] as num?)?.toDouble(),
      errorMessage: json['error_message'] as String?,
    );
  }
}

class SentimentApi {
  final Dio _dio;
  SentimentApi(this._dio);

  Future<Map<String, dynamic>> create(String minutesTaskId) async {
    final response = await _dio.post('/sentiment', data: {
      'minutes_task_id': minutesTaskId,
    });
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getStatus(String taskId) async {
    final response = await _dio.get('/sentiment/$taskId/status');
    return response.data as Map<String, dynamic>;
  }

  // 하위 호환성 유지: 기존 호출자는 List<SentimentSegment>를 계속 받음 (REQ-SEN-011)
  Future<List<SentimentSegment>> getResult(String taskId) async {
    final response = await _dio.get('/sentiment/$taskId');
    final segments = response.data['segments'] as List? ?? [];
    return segments
        .map((e) => SentimentSegment.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // 하위 호환성 유지: 기존 호출자는 List<SentimentSegment>를 계속 받음 (REQ-SEN-011)
  Future<List<SentimentSegment>> getByMeeting(String meetingId) async {
    final response = await _dio.get('/sentiment/meeting/$meetingId');
    final segments = response.data['segments'] as List? ?? [];
    return segments
        .map((e) => SentimentSegment.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // SPEC-SENTIMENT-001: 전체 응답 조회 (speakers + emotional_timeline 포함)
  // REQ-SEN-008: SpeakerSentiment precomputed 데이터 접근
  // REQ-SEN-009: emotional_timeline 데이터 접근
  Future<SentimentFullResponse> getFullByMeeting(String meetingId) async {
    final response = await _dio.get('/sentiment/meeting/$meetingId');
    return SentimentFullResponse.fromJson(response.data as Map<String, dynamic>);
  }

  // SPEC-SENTIMENT-001: 전체 응답 조회 (task_id 기반)
  Future<SentimentFullResponse> getFullResult(String taskId) async {
    final response = await _dio.get('/sentiment/$taskId');
    return SentimentFullResponse.fromJson(response.data as Map<String, dynamic>);
  }
}
