// 화자 분리(Diarization) API 서비스
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

// DiarizationApi 프로바이더
final diarizationApiProvider = Provider<DiarizationApi>((ref) {
  final dio = ref.watch(dioProvider);
  return DiarizationApi(dio);
});

class DiarizationApi {
  final Dio _dio;

  DiarizationApi(this._dio);

  // STT 태스크 ID로 화자 분리 태스크 생성
  Future<Map<String, dynamic>> create(
    String sttTaskId, {
    int? numSpeakers,
    int? minSpeakers,
    int? maxSpeakers,
  }) async {
    final data = <String, dynamic>{'stt_task_id': sttTaskId};
    if (numSpeakers != null) {
      data['num_speakers'] = numSpeakers;
    } else {
      if (minSpeakers != null) {
        data['min_speakers'] = minSpeakers;
      }
      if (maxSpeakers != null) {
        data['max_speakers'] = maxSpeakers;
      }
    }

    final response = await _dio.post('/diarizations', data: data);
    return response.data as Map<String, dynamic>;
  }

  // 태스크 상태 조회
  Future<Map<String, dynamic>> getStatus(String taskId) async {
    final response = await _dio.get('/diarizations/$taskId/status');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 결과 조회
  Future<Map<String, dynamic>> getResult(String taskId) async {
    final response = await _dio.get('/diarizations/$taskId/result');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 삭제
  Future<void> delete(String taskId) async {
    await _dio.delete('/diarizations/$taskId');
  }
}
