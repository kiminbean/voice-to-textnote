import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

final bookmarkApiProvider = Provider<BookmarkApi>((ref) {
  final dio = ref.watch(dioProvider);
  return BookmarkApi(dio);
});

class Bookmark {
  final String id;
  final String taskId;
  final double segmentStart;
  final double segmentEnd;
  final String? textSnippet;
  final String? note;
  final String? color;
  final String createdAt;

  const Bookmark({
    required this.id,
    required this.taskId,
    required this.segmentStart,
    required this.segmentEnd,
    this.textSnippet,
    this.note,
    this.color,
    required this.createdAt,
  });

  factory Bookmark.fromJson(Map<String, dynamic> json) => Bookmark(
        id: json['id'] as String,
        taskId: json['task_id'] as String,
        segmentStart: (json['segment_start'] as num).toDouble(),
        segmentEnd: (json['segment_end'] as num).toDouble(),
        textSnippet: json['text_snippet'] as String?,
        note: json['note'] as String?,
        color: json['color'] as String?,
        createdAt: json['created_at'] as String,
      );
}

class BookmarkApi {
  final Dio _dio;
  BookmarkApi(this._dio);

  Future<List<Bookmark>> list({String? taskId}) async {
    final params = <String, dynamic>{};
    if (taskId != null) params['task_id'] = taskId;
    final response = await _dio.get('/bookmarks', queryParameters: params);
    final data = response.data as Map<String, dynamic>;
    final items = data['bookmarks'] as List;
    return items
        .map((e) => Bookmark.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Bookmark> create({
    required String taskId,
    required double segmentStart,
    required double segmentEnd,
    String? textSnippet,
    String? note,
    String? color,
  }) async {
    final response = await _dio.post('/bookmarks', data: {
      'task_id': taskId,
      'segment_start': segmentStart,
      'segment_end': segmentEnd,
      if (textSnippet != null) 'text_snippet': textSnippet,
      if (note != null) 'note': note,
      if (color != null) 'color': color,
    });
    return Bookmark.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Bookmark> update(String bookmarkId, {String? note, String? color}) async {
    final response = await _dio.patch('/bookmarks/$bookmarkId', data: {
      if (note != null) 'note': note,
      if (color != null) 'color': color,
    });
    return Bookmark.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> delete(String bookmarkId) async {
    await _dio.delete('/bookmarks/$bookmarkId');
  }
}
