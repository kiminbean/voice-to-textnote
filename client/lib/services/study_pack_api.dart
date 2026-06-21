import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/study_pack.dart';

import 'api_client.dart';

final studyPackApiProvider = Provider<StudyPackApi>((ref) {
  final dio = ref.watch(dioProvider);
  return StudyPackApi(dio);
});

class StudyPackApi {
  final Dio _dio;

  StudyPackApi(this._dio);

  Future<StudyPack> create(
    String minutesTaskId, {
    String mode = 'lecture',
    String language = 'ko',
    bool forceRefresh = false,
  }) async {
    final response = await _dio.post(
      '/minutes/$minutesTaskId/study-pack',
      data: {
        'mode': mode,
        'language': language,
        'force_refresh': forceRefresh,
      },
    );
    return StudyPack.fromJson(response.data as Map<String, dynamic>);
  }

  Future<StudyPack> get(
    String minutesTaskId, {
    String mode = 'lecture',
    String language = 'ko',
  }) async {
    final response = await _dio.get(
      '/minutes/$minutesTaskId/study-pack',
      queryParameters: {'mode': mode},
    );
    return StudyPack.fromJson(response.data as Map<String, dynamic>);
  }
}
