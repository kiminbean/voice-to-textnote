// 검색 상태 프로바이더 (SPEC-SEARCH-001)
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/search_result.dart';
import 'package:voice_to_textnote/services/search_api.dart';

// 검색 파라미터 모델 (FutureProvider.family 키로 사용)
class SearchQuery {
  // 검색어
  final String query;

  // 태스크 유형 필터 (null = 전체)
  final String? taskType;

  // 페이지 번호
  final int page;

  const SearchQuery({
    required this.query,
    this.taskType,
    this.page = 1,
  });

  // FutureProvider.family 키 비교를 위한 동등성 구현
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SearchQuery &&
          runtimeType == other.runtimeType &&
          query == other.query &&
          taskType == other.taskType &&
          page == other.page;

  @override
  int get hashCode => Object.hash(query, taskType, page);
}

// 현재 검색어 상태 프로바이더
final searchQueryProvider = StateProvider<String>((ref) => '');

// 검색 결과 프로바이더 (검색어 2자 미만이면 API 미호출)
// @MX:NOTE: query.length < 2이면 빈 결과 반환 (불필요한 API 호출 방지)
final searchResultProvider =
    FutureProvider.family<SearchResponse, SearchQuery>((ref, searchQuery) async {
  // 2자 미만이면 빈 결과 즉시 반환
  if (searchQuery.query.length < 2) {
    return SearchResponse(
      items: const [],
      total: 0,
      page: 1,
      pageSize: 20,
      query: searchQuery.query,
    );
  }

  final api = ref.watch(searchApiProvider);
  return api.search(
    searchQuery.query,
    taskType: searchQuery.taskType,
    page: searchQuery.page,
  );
});
