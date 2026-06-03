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

  // 전문 검색 요청 (SPEC-SEARCH-002 Phase 3 확장)
  // request: 검색 요청 파라미터 (SearchRequest 모델)
  Future<SearchResponse> search(SearchRequest request) async {
    final response = await _dio.get(
      '/search',
      queryParameters: request.toQueryParams(),
    );
    return SearchResponse.fromJson(response.data as Map<String, dynamic>);
  }

  // 자동완성 제안 요청 (SPEC-SEARCH-002 Phase 3)
  // prefix: 검색어 접두사
  Future<SuggestionResponse> getSuggestions(String prefix) async {
    final response = await _dio.get(
      '/search/suggestions',
      queryParameters: {'q': prefix},
    );
    return SuggestionResponse.fromJson(response.data as Map<String, dynamic>);
  }
}
