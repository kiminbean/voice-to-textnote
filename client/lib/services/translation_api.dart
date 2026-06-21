import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/translation.dart';

import 'api_client.dart';

final translationApiProvider = Provider<TranslationApi>((ref) {
  final dio = ref.watch(dioProvider);
  return TranslationApi(dio);
});

class TranslationApi {
  final Dio _dio;

  TranslationApi(this._dio);

  Future<TranslationResult> create(
    String taskId, {
    required String targetLanguage,
    String? sourceLanguage,
    String sourceType = 'auto',
    bool forceRefresh = false,
  }) async {
    final response = await _dio.post(
      '/minutes/$taskId/translation',
      data: {
        'target_language': targetLanguage,
        if (sourceLanguage != null) 'source_language': sourceLanguage,
        'source_type': sourceType,
        'force_refresh': forceRefresh,
      },
    );
    return TranslationResult.fromJson(response.data as Map<String, dynamic>);
  }

  Future<TranslationResult> get(
    String taskId, {
    required String targetLanguage,
    String sourceType = 'auto',
  }) async {
    final response = await _dio.get(
      '/minutes/$taskId/translation',
      queryParameters: {
        'target_language': targetLanguage,
        'source_type': sourceType,
      },
    );
    return TranslationResult.fromJson(response.data as Map<String, dynamic>);
  }
}
