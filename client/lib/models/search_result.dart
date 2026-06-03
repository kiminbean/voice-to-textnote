// 검색 결과 데이터 모델 (SPEC-SEARCH-001)
// @MX:NOTE: 백엔드 SearchResponse 스키마와 1:1 매핑

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
