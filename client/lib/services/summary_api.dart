// AI 요약 API 서비스
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

// SummaryApi 프로바이더
final summaryApiProvider = Provider<SummaryApi>((ref) {
  final dio = ref.watch(dioProvider);
  return SummaryApi(dio);
});

class SummaryApi {
  final Dio _dio;

  SummaryApi(this._dio);

  // 회의록 태스크 ID로 요약 생성
  Future<Map<String, dynamic>> create(String minTaskId) async {
    final response = await _dio.post('/sum/create', data: {'min_task_id': minTaskId});
    return response.data as Map<String, dynamic>;
  }

  // 태스크 상태 조회
  Future<Map<String, dynamic>> getStatus(String taskId) async {
    final response = await _dio.get('/sum/$taskId/status');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 결과 조회
  Future<Map<String, dynamic>> getResult(String taskId) async {
    final response = await _dio.get('/sum/$taskId/result');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 삭제
  Future<void> delete(String taskId) async {
    await _dio.delete('/sum/$taskId');
  }
}
