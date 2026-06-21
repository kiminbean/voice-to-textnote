// 회의 Q&A API 서비스 — SPEC-QA-001
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

final qaApiProvider = Provider<QAApi>((ref) {
  final dio = ref.watch(dioProvider);
  return QAApi(dio);
});

class QAApi {
  final Dio _dio;

  QAApi(this._dio);

  /// 회의 내용에 대해 질문
  Future<QAResponse> ask({
    required String taskId,
    required String question,
    String? threadId,
  }) async {
    final res = await _dio.post('/qa/ask', data: {
      'task_id': taskId,
      'question': question,
      if (threadId != null) 'thread_id': threadId,
    });
    return QAResponse.fromJson(res.data as Map<String, dynamic>);
  }

  /// 여러 회의/요약에서 질문과 관련된 근거 검색
  Future<CrossMeetingAskResponse> askAcross({
    required String question,
    int limit = 5,
  }) async {
    final res = await _dio.post('/qa/ask-across', data: {
      'question': question,
      'limit': limit,
    });
    return CrossMeetingAskResponse.fromJson(res.data as Map<String, dynamic>);
  }

  /// Q&A 이력 조회
  Future<QAHistoryResponse> getHistory(String taskId) async {
    final res = await _dio.get('/qa/$taskId/history');
    return QAHistoryResponse.fromJson(res.data as Map<String, dynamic>);
  }
}

class CrossMeetingSource {
  final String taskId;
  final String taskType;
  final String snippet;
  final String createdAt;
  final String? completedAt;

  const CrossMeetingSource({
    required this.taskId,
    required this.taskType,
    required this.snippet,
    required this.createdAt,
    this.completedAt,
  });

  factory CrossMeetingSource.fromJson(Map<String, dynamic> json) =>
      CrossMeetingSource(
        taskId: json['task_id'] as String,
        taskType: json['task_type'] as String,
        snippet: json['snippet'] as String? ?? '',
        createdAt: json['created_at'] as String,
        completedAt: json['completed_at'] as String?,
      );
}

class CrossMeetingAskResponse {
  final String answer;
  final List<CrossMeetingSource> sources;
  final String query;
  final int total;

  const CrossMeetingAskResponse({
    required this.answer,
    required this.sources,
    required this.query,
    required this.total,
  });

  factory CrossMeetingAskResponse.fromJson(Map<String, dynamic> json) =>
      CrossMeetingAskResponse(
        answer: json['answer'] as String? ?? '',
        sources: (json['sources'] as List<dynamic>? ?? [])
            .map((e) => CrossMeetingSource.fromJson(e as Map<String, dynamic>))
            .toList(),
        query: json['query'] as String? ?? '',
        total: json['total'] as int? ?? 0,
      );
}

class QASource {
  final int segmentIndex;
  final String? speaker;
  final String text;

  const QASource({
    required this.segmentIndex,
    this.speaker,
    required this.text,
  });

  factory QASource.fromJson(Map<String, dynamic> json) => QASource(
        segmentIndex: json['segment_index'] as int,
        speaker: json['speaker'] as String?,
        text: json['text'] as String,
      );
}

class QAResponse {
  final String answer;
  final List<QASource> sources;
  final String threadId;

  const QAResponse({
    required this.answer,
    required this.sources,
    required this.threadId,
  });

  factory QAResponse.fromJson(Map<String, dynamic> json) => QAResponse(
        answer: json['answer'] as String,
        sources: (json['sources'] as List<dynamic>)
            .map((e) => QASource.fromJson(e as Map<String, dynamic>))
            .toList(),
        threadId: json['thread_id'] as String,
      );
}

class QAHistoryItem {
  final String question;
  final String answer;
  final List<QASource> sources;
  final String createdAt;

  const QAHistoryItem({
    required this.question,
    required this.answer,
    required this.sources,
    required this.createdAt,
  });

  factory QAHistoryItem.fromJson(Map<String, dynamic> json) => QAHistoryItem(
        question: json['question'] as String,
        answer: json['answer'] as String,
        sources: (json['sources'] as List<dynamic>?)
                ?.map((e) => QASource.fromJson(e as Map<String, dynamic>))
                .toList() ??
            [],
        createdAt: json['created_at'] as String,
      );
}

class QAHistoryResponse {
  final List<QAHistoryItem> items;
  final int total;

  const QAHistoryResponse({required this.items, required this.total});

  factory QAHistoryResponse.fromJson(Map<String, dynamic> json) =>
      QAHistoryResponse(
        items: (json['items'] as List<dynamic>)
            .map((e) => QAHistoryItem.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: json['total'] as int,
      );
}
