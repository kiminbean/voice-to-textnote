// 이력 API 서비스 - SPEC-HISTSYNC-001 REQ-HSYNC-001
// @MX:ANCHOR: HistoryApi - 서버 이력 조회/삭제의 단일 진입점
// @MX:REASON: meetingListProvider와 홈 화면에서 참조하는 핵심 서비스
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

// HistoryApi 프로바이더
final historyApiProvider = Provider<HistoryApi>((ref) {
  final dio = ref.watch(dioProvider);
  return HistoryApi(dio);
});

class HistoryApi {
  final Dio _dio;

  HistoryApi(this._dio);

  // 이력 목록 조회 (페이지네이션, 필터 지원)
  // taskType: 작업 유형 필터 (summary, minutes 등, null = 전체)
  // status: 상태 필터 (completed, failed 등, null = 전체)
  Future<Map<String, dynamic>> list({
    String? taskType,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    // null이 아닌 파라미터만 쿼리에 포함
    final queryParameters = <String, dynamic>{
      'page': page,
      'page_size': pageSize,
    };
    if (taskType != null) queryParameters['task_type'] = taskType;
    if (status != null) queryParameters['status'] = status;

    final response = await _dio.get(
      '/history',
      queryParameters: queryParameters,
    );
    return response.data as Map<String, dynamic>;
  }

  // 이력 단건 상세 조회 (result_data 포함)
  Future<Map<String, dynamic>> get(String taskId) async {
    final response = await _dio.get('/history/$taskId');
    return response.data as Map<String, dynamic>;
  }

  // 이력 삭제 (서버에서 제거)
  Future<void> delete(String taskId) async {
    await _dio.delete('/history/$taskId');
  }
}
