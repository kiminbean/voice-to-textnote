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

  Future<List<SentimentSegment>> getResult(String taskId) async {
    final response = await _dio.get('/sentiment/$taskId');
    final segments = response.data['segments'] as List? ?? [];
    return segments
        .map((e) => SentimentSegment.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<SentimentSegment>> getByMeeting(String meetingId) async {
    final response = await _dio.get('/sentiment/meeting/$meetingId');
    final segments = response.data['segments'] as List? ?? [];
    return segments
        .map((e) => SentimentSegment.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
