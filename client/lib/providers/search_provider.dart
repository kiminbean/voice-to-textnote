// 검색 상태 프로바이더 (SPEC-SEARCH-001 → SPEC-SEARCH-002 Phase 3 확장)
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/search_result.dart';
import 'package:voice_to_textnote/services/search_api.dart';

// 검색 요청 상태 프로바이더
class SearchFilterState {
  // 정렬 순서 ('relevance', 'newest', 'oldest')
  final String? sort;

  // 시작 날짜 (ISO 8601: yyyy-MM-dd)
  final String? dateFrom;

  // 종료 날짜 (ISO 8601: yyyy-MM-dd)
  final String? dateTo;

  // 발언자 이름
  final String? speaker;

  // 행동 항목 포함 필터
  final bool? hasActionItems;

  // 핵심 결정 사항 포함 필터
  final bool? hasKeyDecisions;

  const SearchFilterState({
    this.sort = 'relevance',
    this.dateFrom,
    this.dateTo,
    this.speaker,
    this.hasActionItems,
    this.hasKeyDecisions,
  });

  /// 필터가 적용되어 있는지 확인
  bool get hasFilters =>
      dateFrom != null ||
      dateTo != null ||
      speaker != null ||
      hasActionItems != null ||
      hasKeyDecisions != null;

  /// SearchFilterState 복사
  SearchFilterState copyWith({
    String? sort,
    String? dateFrom,
    String? dateTo,
    String? speaker,
    bool? hasActionItems,
    bool? hasKeyDecisions,
    bool clearDateFrom = false,
    bool clearDateTo = false,
    bool clearSpeaker = false,
    bool clearHasActionItems = false,
    bool clearHasKeyDecisions = false,
  }) {
    return SearchFilterState(
      sort: sort ?? this.sort,
      dateFrom: clearDateFrom ? null : (dateFrom ?? this.dateFrom),
      dateTo: clearDateTo ? null : (dateTo ?? this.dateTo),
      speaker: clearSpeaker ? null : (speaker ?? this.speaker),
      hasActionItems:
          clearHasActionItems ? null : (hasActionItems ?? this.hasActionItems),
      hasKeyDecisions:
          clearHasKeyDecisions ? null : (hasKeyDecisions ?? this.hasKeyDecisions),
    );
  }

  /// 모든 필터 초기화
  SearchFilterState clear() {
    return const SearchFilterState(sort: 'relevance');
  }
}

// 검색 필터 상태 프로바이더 (SPEC-SEARCH-002 Phase 3)
final searchFilterProvider =
    StateProvider<SearchFilterState>((ref) => const SearchFilterState());

// 자동완성 제안 상태 프로바이더 (SPEC-SEARCH-002 Phase 5)
final suggestionsProvider =
    FutureProvider.family<List<String>, String>((ref, prefix) async {
  if (prefix.length < 2) {
    return const [];
  }

  final api = ref.watch(searchApiProvider);
  final response = await api.getSuggestions(prefix);
  return response.suggestions;
});

// 최근 검색어 상태 프로바이더 (SPEC-SEARCH-002 Phase 5)
// SharedPreferences에 저장하므로 초기값은 빈 리스트
final recentSearchesProvider = StateProvider<List<String>>((ref) => const []);

// 검색 결과 프로바이더 (SearchRequest 기반, SPEC-SEARCH-002 Phase 3)
final searchResultProvider =
    FutureProvider.family<SearchResponse, SearchRequest>((ref, request) async {
  // 2자 미만이면 빈 결과 즉시 반환
  if (request.query.length < 2) {
    return SearchResponse(
      items: const [],
      total: 0,
      page: 1,
      pageSize: request.pageSize,
      query: request.query,
    );
  }

  final api = ref.watch(searchApiProvider);
  return api.search(request);
});
