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
  // templateId: 양식 기반 요약 시 사용 (null = 기본 양식, SPEC-TMPL-001 REQ-TMPL-006)
  Future<Map<String, dynamic>> create(String minTaskId,
      {String? templateId}) async {
    final Map<String, dynamic> data = {'minutes_task_id': minTaskId};
    if (templateId != null) {
      data['template_id'] = templateId;
    }
    final response = await _dio.post('/summaries', data: data);
    return response.data as Map<String, dynamic>;
  }

  // 태스크 상태 조회
  Future<Map<String, dynamic>> getStatus(String taskId) async {
    final response = await _dio.get('/summaries/$taskId/status');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 결과 조회
  Future<Map<String, dynamic>> getResult(String taskId) async {
    final response = await _dio.get('/summaries/$taskId');
    return response.data as Map<String, dynamic>;
  }

  // 회의록 태스크 ID로 목적별 스마트 요약 생성
  Future<Map<String, dynamic>> createSmartSummary(
    String minutesTaskId, {
    required String summaryMode,
    String length = 'medium',
    List<String> focusAreas = const ['all'],
    bool includeSentiment = true,
  }) async {
    final response = await _dio.post(
      '/smart-summary/$minutesTaskId',
      data: {
        'summary_mode': summaryMode,
        'length': length,
        'focus_areas': focusAreas,
        'include_sentiment': includeSentiment,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  // 사용 가능한 목적별 스마트 요약 모드 조회
  Future<List<Map<String, dynamic>>> getSmartSummaryModes() async {
    final response = await _dio.get('/smart-summary/modes');
    final data = response.data as Map<String, dynamic>;
    final modes = data['modes'] as List<dynamic>? ?? [];
    return modes.cast<Map<String, dynamic>>();
  }

  // 완료된 요약 태스크 ID로 관계 추론형 마인드맵 생성
  Future<Map<String, dynamic>> createMindMap(
    String summaryTaskId, {
    int maxTokens = 2048,
  }) async {
    final response = await _dio.post(
      '/summaries/$summaryTaskId/mind-map',
      data: {'max_tokens': maxTokens},
    );
    return response.data as Map<String, dynamic>;
  }

  // 마인드맵 태스크 상태 조회
  Future<Map<String, dynamic>> getMindMapStatus(String taskId) async {
    final response = await _dio.get('/summaries/mind-map/$taskId/status');
    return response.data as Map<String, dynamic>;
  }

  // 마인드맵 태스크 결과 조회
  Future<Map<String, dynamic>> getMindMapResult(String taskId) async {
    final response = await _dio.get('/summaries/mind-map/$taskId');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 삭제
  Future<void> delete(String taskId) async {
    await _dio.delete('/summaries/$taskId');
  }
}
