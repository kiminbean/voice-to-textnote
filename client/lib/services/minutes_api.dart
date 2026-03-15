// 회의록 생성 API 서비스
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
  Future<Map<String, dynamic>> create(String diaTaskId) async {
    final response = await _dio.post('/min/create', data: {'dia_task_id': diaTaskId});
    return response.data as Map<String, dynamic>;
  }

  // 태스크 상태 조회
  Future<Map<String, dynamic>> getStatus(String taskId) async {
    final response = await _dio.get('/min/$taskId/status');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 결과 조회
  Future<Map<String, dynamic>> getResult(String taskId) async {
    final response = await _dio.get('/min/$taskId/result');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 삭제
  Future<void> delete(String taskId) async {
    await _dio.delete('/min/$taskId');
  }
}
