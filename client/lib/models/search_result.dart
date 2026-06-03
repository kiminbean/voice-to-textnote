// 검색 결과 데이터 모델 (SPEC-SEARCH-001)
// @MX:NOTE: 백엔드 SearchResponse 스키마와 1:1 매핑

// 검색 요청 파라미터 모델 (SPEC-SEARCH-002 Phase 3)
class SearchRequest {
  // 검색어
  final String query;

  // 태스크 유형 필터 ('all', 'minutes', 'summary')
  final String? taskType;

  // 페이지 번호 (1부터 시작)
  final int page;

  // 페이지당 결과 수
  final int pageSize;

  // 정렬 순서 ('relevance', 'newest', 'oldest')
  final String? sort;

  // 시작 날짜 (ISO 8601 형식: yyyy-MM-dd)
  final String? dateFrom;

  // 종료 날짜 (ISO 8601 형식: yyyy-MM-dd)
  final String? dateTo;

  // 발언자 이름 필터
  final String? speaker;

  // 행동 항목 포함 여부 필터
  final bool? hasActionItems;

  // 핵심 결정 사항 포함 여부 필터
  final bool? hasKeyDecisions;

  const SearchRequest({
    required this.query,
    this.taskType,
    this.page = 1,
    this.pageSize = 20,
    this.sort,
    this.dateFrom,
    this.dateTo,
    this.speaker,
    this.hasActionItems,
    this.hasKeyDecisions,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SearchRequest &&
          query == other.query &&
          taskType == other.taskType &&
          page == other.page &&
          pageSize == other.pageSize &&
          sort == other.sort &&
          dateFrom == other.dateFrom &&
          dateTo == other.dateTo &&
          speaker == other.speaker &&
          hasActionItems == other.hasActionItems &&
          hasKeyDecisions == other.hasKeyDecisions;

  @override
  int get hashCode => Object.hash(
        query,
        taskType,
        page,
        pageSize,
        sort,
        dateFrom,
        dateTo,
        speaker,
        hasActionItems,
        hasKeyDecisions,
      );

  /// null이 아닌 파라미터만 쿼리 파라미터 Map으로 변환
  Map<String, String> toQueryParams() {
    final params = <String, String>{
      'q': query,
      'page': page.toString(),
      'page_size': pageSize.toString(),
    };

    if (taskType != null && taskType != 'all') {
      params['task_type'] = taskType!;
    }

    if (sort != null) {
      params['sort'] = sort!;
    }

    if (dateFrom != null) {
      params['date_from'] = dateFrom!;
    }

    if (dateTo != null) {
      params['date_to'] = dateTo!;
    }

    if (speaker != null && speaker!.isNotEmpty) {
      params['speaker'] = speaker!;
    }

    if (hasActionItems != null) {
      params['has_action_items'] = hasActionItems.toString();
    }

    if (hasKeyDecisions != null) {
      params['has_key_decisions'] = hasKeyDecisions.toString();
    }

    return params;
  }

  /// SearchRequest 복사 (일부 필드만 변경)
  SearchRequest copyWith({
    String? query,
    String? taskType,
    int? page,
    int? pageSize,
    String? sort,
    String? dateFrom,
    String? dateTo,
    String? speaker,
    bool? hasActionItems,
    bool? hasKeyDecisions,
  }) {
    return SearchRequest(
      query: query ?? this.query,
      taskType: taskType ?? this.taskType,
      page: page ?? this.page,
      pageSize: pageSize ?? this.pageSize,
      sort: sort ?? this.sort,
      dateFrom: dateFrom ?? this.dateFrom,
      dateTo: dateTo ?? this.dateTo,
      speaker: speaker ?? this.speaker,
      hasActionItems: hasActionItems ?? this.hasActionItems,
      hasKeyDecisions: hasKeyDecisions ?? this.hasKeyDecisions,
    );
  }
}

// 개별 검색 결과 항목
class SearchResultItem {
  // 태스크 고유 식별자
  final String taskId;

  // 태스크 유형 ('minutes' 또는 'summary')
  final String taskType;

  // 검색어가 포함된 스니펫 (<b>태그로 강조)
  final String snippet;

  // 생성 일시
  final DateTime createdAt;

  // 완료 일시 (처리 중이면 null)
  final DateTime? completedAt;

  const SearchResultItem({
    required this.taskId,
    required this.taskType,
    required this.snippet,
    required this.createdAt,
    this.completedAt,
  });

  factory SearchResultItem.fromJson(Map<String, dynamic> json) {
    return SearchResultItem(
      taskId: json['task_id'] as String,
      taskType: json['task_type'] as String,
      snippet: json['snippet'] as String? ?? '',
      createdAt: DateTime.parse(json['created_at'] as String),
      completedAt: json['completed_at'] != null
          ? DateTime.parse(json['completed_at'] as String)
          : null,
    );
  }

  /// SearchResultItem을 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'task_id': taskId,
      'task_type': taskType,
      'snippet': snippet,
      'created_at': createdAt.toIso8601String(),
      'completed_at': completedAt?.toIso8601String(),
    };
  }
}

// 검색 응답 전체 (페이지네이션 포함)
class SearchResponse {
  // 검색 결과 항목 목록
  final List<SearchResultItem> items;

  // 전체 결과 수
  final int total;

  // 현재 페이지 번호
  final int page;

  // 페이지당 결과 수
  final int pageSize;

  // 검색어
  final String query;

  const SearchResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.query,
  });

  factory SearchResponse.fromJson(Map<String, dynamic> json) {
    return SearchResponse(
      items: (json['items'] as List<dynamic>)
          .map(
            (item) =>
                SearchResultItem.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
      total: json['total'] as int? ?? 0,
      page: json['page'] as int? ?? 1,
      pageSize: json['page_size'] as int? ?? 20,
      query: json['query'] as String? ?? '',
    );
  }

  /// SearchResponse를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'items': items.map((e) => e.toJson()).toList(),
      'total': total,
      'page': page,
      'page_size': pageSize,
      'query': query,
    };
  }

  /// 전체 페이지 수 계산
  int get totalPages => (total / pageSize).ceil();

  /// 첫 페이지인지 확인
  bool get isFirstPage => page <= 1;

  /// 마지막 페이지인지 확인
  bool get isLastPage => page >= totalPages;
}

// 자동완성 제안 응답 모델 (SPEC-SEARCH-002 Phase 3)
class SuggestionResponse {
  // 제안 목록
  final List<String> suggestions;

  // 원본 검색어 접두사
  final String query;

  const SuggestionResponse({
    required this.suggestions,
    required this.query,
  });

  factory SuggestionResponse.fromJson(Map<String, dynamic> json) {
    return SuggestionResponse(
      suggestions: (json['suggestions'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      query: json['query'] as String? ?? '',
    );
  }

  /// SuggestionResponse를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'suggestions': suggestions,
      'query': query,
    };
  }
}
