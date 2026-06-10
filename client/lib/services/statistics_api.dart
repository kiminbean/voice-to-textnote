import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

final statisticsApiProvider = Provider<StatisticsApi>((ref) {
  final dio = ref.watch(dioProvider);
  return StatisticsApi(dio);
});

class SpeakerStat {
  final String speaker;
  final double speakingTimeSeconds;
  final double speakingRatio;
  final int segmentCount;
  final int wordCount;

  const SpeakerStat({
    required this.speaker,
    required this.speakingTimeSeconds,
    required this.speakingRatio,
    required this.segmentCount,
    required this.wordCount,
  });

  factory SpeakerStat.fromJson(Map<String, dynamic> json) => SpeakerStat(
        speaker: json['speaker'] as String,
        speakingTimeSeconds: (json['speaking_time_seconds'] as num).toDouble(),
        speakingRatio: (json['speaking_ratio'] as num).toDouble(),
        segmentCount: json['segment_count'] as int,
        wordCount: json['word_count'] as int,
      );
}

class KeywordStat {
  final String keyword;
  final int count;

  const KeywordStat({required this.keyword, required this.count});

  factory KeywordStat.fromJson(Map<String, dynamic> json) => KeywordStat(
        keyword: json['keyword'] as String,
        count: json['count'] as int,
      );
}

class StatisticsResponse {
  final String taskId;
  final int totalSegments;
  final int totalWords;
  final double totalDurationSeconds;
  final int uniqueSpeakers;
  final List<SpeakerStat> speakers;
  final List<KeywordStat> topKeywords;

  const StatisticsResponse({
    required this.taskId,
    required this.totalSegments,
    required this.totalWords,
    required this.totalDurationSeconds,
    required this.uniqueSpeakers,
    required this.speakers,
    required this.topKeywords,
  });

  factory StatisticsResponse.fromJson(Map<String, dynamic> json) =>
      StatisticsResponse(
        taskId: json['task_id'] as String,
        totalSegments: json['total_segments'] as int,
        totalWords: json['total_words'] as int,
        totalDurationSeconds:
            (json['total_duration_seconds'] as num).toDouble(),
        uniqueSpeakers: json['unique_speakers'] as int,
        speakers: (json['speakers'] as List)
            .map((e) => SpeakerStat.fromJson(e as Map<String, dynamic>))
            .toList(),
        topKeywords: (json['top_keywords'] as List)
            .map((e) => KeywordStat.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class StatisticsApi {
  final Dio _dio;
  StatisticsApi(this._dio);

  Future<StatisticsResponse> getStatistics(String taskId) async {
    final response = await _dio.get('/statistics/$taskId');
    return StatisticsResponse.fromJson(response.data as Map<String, dynamic>);
  }
}
