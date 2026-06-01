// 음성 인식(STT) API 서비스
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'api_client.dart';

// TranscriptionApi 프로바이더
final transcriptionApiProvider = Provider<TranscriptionApi>((ref) {
  final dio = ref.watch(dioProvider);
  return TranscriptionApi(dio);
});

class TranscriptionApi {
  final Dio _dio;

  TranscriptionApi(this._dio);

  // 오디오 파일 업로드 (멀티파트) - 대용량 파일용 타임아웃 별도 설정
  // vocabulary_id: STT 정확도 향상용 사용자 사전 ID (선택)
  Future<Map<String, dynamic>> upload(
    String filePath, {
    String? vocabularyId,
  }) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        filePath,
        filename: File(filePath).uri.pathSegments.last,
      ),
      if (vocabularyId != null) 'vocabulary_id': vocabularyId,
    });

    final response = await _dio.post(
      '/transcriptions',
      data: formData,
      options: Options(
        contentType: 'multipart/form-data',
        sendTimeout: AppConfig.uploadSendTimeout,
        receiveTimeout: AppConfig.uploadReceiveTimeout,
      ),
    );

    return response.data as Map<String, dynamic>;
  }

  // 태스크 상태 조회
  Future<Map<String, dynamic>> getStatus(String taskId) async {
    final response = await _dio.get('/transcriptions/$taskId/status');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 결과 조회
  Future<Map<String, dynamic>> getResult(String taskId) async {
    final response = await _dio.get('/transcriptions/$taskId/result');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 삭제
  Future<void> delete(String taskId) async {
    await _dio.delete('/transcriptions/$taskId');
  }
}
