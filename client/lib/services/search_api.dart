// 검색 API 서비스 (SPEC-SEARCH-001)
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/search_result.dart';
import 'package:voice_to_textnote/services/api_client.dart';

// SearchApi 프로바이더
final searchApiProvider = Provider<SearchApi>((ref) {
  final dio = ref.watch(dioProvider);
  return SearchApi(dio);
});

// 회의록/요약 전문 검색 API
class SearchApi {
  final Dio _dio;

  SearchApi(this._dio);

  // 전문 검색 요청
  // query: 검색어 (2자 이상 필요)
  // taskType: 필터 ('minutes', 'summary', null = 전체)
  // page: 페이지 번호 (1부터 시작)
  // pageSize: 페이지당 결과 수
  Future<SearchResponse> search(
    String query, {
    String? taskType,
    int page = 1,
    int pageSize = 20,
  }) async {
    final params = <String, dynamic>{
      'q': query,
      'page': page,
      'page_size': pageSize,
    };

    // 태스크 유형 필터가 있으면 추가
    if (taskType != null) {
      params['task_type'] = taskType;
    }

    final response = await _dio.get('/search', queryParameters: params);
    return SearchResponse.fromJson(response.data as Map<String, dynamic>);
  }
}
