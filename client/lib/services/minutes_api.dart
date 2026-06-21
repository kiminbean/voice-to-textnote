// 회의록 생성 API 서비스
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

// MinutesApi 프로바이더
final minutesApiProvider = Provider<MinutesApi>((ref) {
  final dio = ref.watch(dioProvider);
  return MinutesApi(dio);
});

class MinutesApi {
  final Dio _dio;

  MinutesApi(this._dio);

  // 화자 분리 태스크 ID로 회의록 생성
  //
  // [sttTaskId]가 제공되면 병렬 모드로 매칭됨. STT와 DIA를 동시 시작한 경우
  // DIA 결과가 matched=False일 수 있어 minutes_task가 직접 매칭한다.
  Future<Map<String, dynamic>> create(
    String diaTaskId, {
    String? sttTaskId,
  }) async {
    final data = <String, dynamic>{'diarization_task_id': diaTaskId};
    if (sttTaskId != null) {
      data['stt_task_id'] = sttTaskId;
    }
    final response = await _dio.post('/minutes', data: data);
    return response.data as Map<String, dynamic>;
  }

  // 태스크 상태 조회
  Future<Map<String, dynamic>> getStatus(String taskId) async {
    final response = await _dio.get('/minutes/$taskId/status');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 결과 조회
  Future<Map<String, dynamic>> getResult(String taskId) async {
    final response = await _dio.get('/minutes/$taskId');
    return response.data as Map<String, dynamic>;
  }

  // 사용자가 보유한 외부 URL transcript/text를 회의록 자산으로 가져오기
  Future<Map<String, dynamic>> importExternalText({
    required String sourceUrl,
    required String title,
    required String content,
    String sourceType = 'web',
    String language = 'ko',
  }) async {
    final response = await _dio.post(
      '/imports/external-text',
      data: {
        'source_url': sourceUrl,
        'title': title,
        'content': content,
        'source_type': sourceType,
        'language': language,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  // PDF/DOCX 문서를 검색 가능한 회의록 자산으로 가져오기
  Future<Map<String, dynamic>> importDocument({
    required File file,
    String? title,
    String language = 'ko',
  }) async {
    final fileName = file.path.split('/').last;
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        file.path,
        filename: fileName,
      ),
      if (title != null && title.trim().isNotEmpty) 'title': title.trim(),
      'language': language,
    });

    final response = await _dio.post(
      '/imports/document',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );
    return response.data as Map<String, dynamic>;
  }

  // 태스크 삭제
  Future<void> delete(String taskId) async {
    await _dio.delete('/minutes/$taskId');
  }
}
