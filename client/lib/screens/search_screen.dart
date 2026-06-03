// 검색 화면 (SPEC-SEARCH-001 → SPEC-SEARCH-002 Phase 3-5 확장)
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/models/search_result.dart';
import 'package:voice_to_textnote/providers/search_provider.dart';
import 'package:voice_to_textnote/widgets/recent_searches_widget.dart';
import 'package:voice_to_textnote/widgets/search_filter_bottom_sheet.dart';

// 검색 화면 - 회의록/요약 전문 검색 (필터/정렬/자동완성 포함)
// ConsumerStatefulWidget: 디바운스 타이머와 텍스트 컨트롤러 관리 필요
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  // 텍스트 필드 컨트롤러
  final TextEditingController _controller = TextEditingController();

  // 디바운스 타이머 (300ms)
  Timer? _debounceTimer;

  // 자동완성 디바운스 타이머 (300ms)
  Timer? _suggestionTimer;

  // 현재 실제 검색에 사용 중인 쿼리
  String _activeQuery = '';

  // 검색어 포커스 상태
  bool _isFocused = false;

  // SharedPreferences 인스턴스
  SharedPreferences? _prefs;

  @override
  void initState() {
    super.initState();
    // SharedPreferences 로드
    _loadRecentSearches();
    // 텍스트 변경 감지
    _controller.addListener(_onTextChanged);
    // 포커스 변경 감지
    _controller.addListener(_onFocusChanged);
  }

  @override
  void dispose() {
    // 타이머와 컨트롤러 정리
    _debounceTimer?.cancel();
    _suggestionTimer?.cancel();
    _controller.removeListener(_onTextChanged);
    _controller.removeListener(_onFocusChanged);
    _controller.dispose();
    super.dispose();
  }

  // 최근 검색어 로드
  Future<void> _loadRecentSearches() async {
    _prefs = await SharedPreferences.getInstance();
    final recentSearches = _prefs?.getStringList('recent_searches') ?? [];
    ref.read(recentSearchesProvider.notifier).state = recentSearches;
  }

  // 최근 검색어 저장 (최대 20개)
  Future<void> _saveRecentSearch(String query) async {
    if (query.trim().isEmpty) return;

    final current = ref.read(recentSearchesProvider);
    final updated = [query, ...current]..remove(query); // 중복 제거 및 최신 추가

    // 최대 20개 유지
    final trimmed = updated.take(20).toList();
    ref.read(recentSearchesProvider.notifier).state = trimmed;

    // SharedPreferences에 저장
    await _prefs?.setStringList('recent_searches', trimmed);
  }

  // 텍스트 변경 시 300ms 디바운스 후 검색 실행
  void _onTextChanged() {
    final text = _controller.text.trim();

    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 300), () {
      if (mounted) {
        setState(() {
          _activeQuery = text;
        });
      }
    });
  }

  // 포커스 변경 감지
  void _onFocusChanged() {
    final isFocused = _controller.selection.isValid;
    if (_isFocused != isFocused) {
      setState(() {
        _isFocused = isFocused;
      });
    }
  }

  // 최근 검색어 선택
  void _onSelectRecentSearch(String query) {
    _controller.text = query;
    setState(() {
      _activeQuery = query;
    });
    _saveRecentSearch(query);
  }

  // 최근 검색어 삭제
  void _onDeleteRecentSearch(String query) async {
    final current = ref.read(recentSearchesProvider);
    final updated = [...current]..remove(query);
    ref.read(recentSearchesProvider.notifier).state = updated;
    await _prefs?.setStringList('recent_searches', updated);
  }

  @override
  Widget build(BuildContext context) {
    // 현재 필터 상태 구독
    final filterState = ref.watch(searchFilterProvider);

    // SearchRequest 생성
    final searchRequest = SearchRequest(
      query: _activeQuery,
      page: 1,
      pageSize: 20,
      sort: filterState.sort,
      dateFrom: filterState.dateFrom,
      dateTo: filterState.dateTo,
      speaker: filterState.speaker,
      hasActionItems: filterState.hasActionItems,
      hasKeyDecisions: filterState.hasKeyDecisions,
    );

    // 검색 결과 구독
    final searchResult = ref.watch(searchResultProvider(searchRequest));

    return Scaffold(
      appBar: AppBar(
        // 뒤로가기 버튼 (기본 제공)
        leading: BackButton(onPressed: () => context.pop()),
        // 검색 입력 필드
        title: TextField(
          controller: _controller,
          autofocus: true, // 화면 진입 시 자동 포커스
          decoration: InputDecoration(
            hintText: '검색어를 입력하세요',
            border: InputBorder.none,
            // 정렬 아이콘 추가
            suffixIcon: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // 정렬 드롭다운
                PopupMenuButton<String>(
                  icon: const Icon(Icons.sort),
                  tooltip: '정렬',
                  initialValue: filterState.sort,
                  onSelected: (value) {
                    ref.read(searchFilterProvider.notifier).state =
                        filterState.copyWith(sort: value);
                  },
                  itemBuilder: (context) => [
                    const PopupMenuItem(
                      value: 'relevance',
                      child: Text('관련도순'),
                    ),
                    const PopupMenuItem(
                      value: 'newest',
                      child: Text('최신순'),
                    ),
                    const PopupMenuItem(
                      value: 'oldest',
                      child: Text('오래된순'),
                    ),
                  ],
                ),
                // 필터 버튼
                IconButton(
                  icon: const Icon(Icons.filter_list),
                  tooltip: '필터',
                  onPressed: () => _showFilterBottomSheet(),
                ),
              ],
            ),
          ),
          textInputAction: TextInputAction.search,
          style: const TextStyle(fontSize: 16),
          onTap: () {
            setState(() {
              _isFocused = true;
            });
          },
          onSubmitted: (value) {
            // 검색 제출 시 최근 검색어에 추가
            if (value.trim().isNotEmpty) {
              _saveRecentSearch(value.trim());
            }
          },
        ),
        // 입력 내용 지우기 버튼
        actions: [
          if (_controller.text.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.clear),
              tooltip: '지우기',
              onPressed: () {
                _controller.clear();
                setState(() {
                  _activeQuery = '';
                });
              },
            ),
        ],
      ),
      body: _buildBody(searchResult, filterState),
    );
  }

  // 필터 bottom sheet 표시
  void _showFilterBottomSheet() {
    final filterState = ref.read(searchFilterProvider);
    showModalBottomSheet<SearchFilterState>(
      context: context,
      isScrollControlled: true,
      builder: (context) => SearchFilterBottomSheet(
        initialFilter: filterState,
      ),
    );
  }

  // 검색 결과 본문 빌드
  Widget _buildBody(
    AsyncValue<SearchResponse> result,
    SearchFilterState filterState,
  ) {
    // 검색어 없음: 최근 검색어 표시 (Phase 5)
    if (_activeQuery.isEmpty) {
      return RecentSearchesWidget(
        recentSearchesProvider: recentSearchesProvider,
        onSearch: _onSelectRecentSearch,
      );
    }

    // 로딩 상태
    if (result.isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    // 에러 상태
    if (result.hasError) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            const Text('검색 중 오류가 발생했습니다'),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () {
                // 동일 요청으로 재시도
                final filterState = ref.read(searchFilterProvider);
                final request = SearchRequest(
                  query: _activeQuery,
                  page: 1,
                  pageSize: 20,
                  sort: filterState.sort,
                  dateFrom: filterState.dateFrom,
                  dateTo: filterState.dateTo,
                  speaker: filterState.speaker,
                  hasActionItems: filterState.hasActionItems,
                  hasKeyDecisions: filterState.hasKeyDecisions,
                );
                ref.invalidate(searchResultProvider(request));
              },
              child: const Text('다시 시도'),
            ),
          ],
        ),
      );
    }

    final response = result.value!;

    // 검색 결과 없음
    if (response.items.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.search_off, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            const Text(
              '검색 결과가 없습니다',
              style: TextStyle(color: Colors.grey, fontSize: 16),
            ),
            if (filterState.hasFilters) ...[
              const SizedBox(height: 8),
              TextButton(
                onPressed: () {
                  ref.read(searchFilterProvider.notifier).state =
                      filterState.clear();
                },
                child: const Text('필터 초기화'),
              ),
            ],
          ],
        ),
      );
    }

    // 활성 필터 칩 (Phase 4)
    final activeFilters = _buildActiveFilterChips(filterState);

    return Column(
      children: [
        // 활성 필터 칩
        if (activeFilters.isNotEmpty)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: activeFilters,
            ),
          ),
        // 검색 결과 목록
        Expanded(
          child: ListView.builder(
            itemCount: response.items.length,
            itemBuilder: (context, index) {
              final item = response.items[index];
              return _SearchResultTile(
                item: item,
                onTap: () => context.push('/result/${item.taskId}'),
              );
            },
          ),
        ),
      ],
    );
  }

  // 활성 필터 칩 빌드
  List<Widget> _buildActiveFilterChips(SearchFilterState filterState) {
    final chips = <Widget>[];

    // 정렬
    if (filterState.sort != null && filterState.sort != 'relevance') {
      final sortLabel = switch (filterState.sort) {
        'newest' => '최신순',
        'oldest' => '오래된순',
        _ => '관련도순',
      };
      chips.add(_FilterChip(
        label: sortLabel,
        onDeleted: () {
          ref.read(searchFilterProvider.notifier).state =
              filterState.copyWith(sort: 'relevance');
        },
      ));
    }

    // 날짜 범위
    if (filterState.dateFrom != null || filterState.dateTo != null) {
      final dateLabel = [
        if (filterState.dateFrom != null) filterState.dateFrom,
        if (filterState.dateTo != null) filterState.dateTo,
      ].join(' ~ ');
      chips.add(_FilterChip(
        label: '날짜: $dateLabel',
        onDeleted: () {
          ref.read(searchFilterProvider.notifier).state =
              filterState.copyWith(clearDateFrom: true, clearDateTo: true);
        },
      ));
    }

    // 발언자
    if (filterState.speaker != null && filterState.speaker!.isNotEmpty) {
      chips.add(_FilterChip(
        label: '발언자: ${filterState.speaker}',
        onDeleted: () {
          ref.read(searchFilterProvider.notifier).state =
              filterState.copyWith(clearSpeaker: true);
        },
      ));
    }

    // 행동 항목
    if (filterState.hasActionItems == true) {
      chips.add(const _FilterChip(
        label: '행동 항목',
        onDeleted: null, // 정렬은 항상 표시
      ));
    }

    // 핵심 결정 사항
    if (filterState.hasKeyDecisions == true) {
      chips.add(const _FilterChip(
        label: '핵심 결정',
        onDeleted: null, // 정렬은 항상 표시
      ));
    }

    return chips;
  }
}

// 개별 검색 결과 타일
class _SearchResultTile extends StatelessWidget {
  final SearchResultItem item;
  final VoidCallback onTap;

  const _SearchResultTile({
    required this.item,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    // 태스크 유형별 아이콘 설정
    final icon = item.taskType == 'minutes'
        ? Icons.description
        : Icons.summarize;
    final typeLabel = item.taskType == 'minutes' ? '회의록' : '요약';

    return ListTile(
      leading: Icon(icon, color: Theme.of(context).colorScheme.primary),
      title: Text(
        typeLabel,
        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 4),
          // 스니펫 (볼드 강조 파싱)
          Text.rich(
            TextSpan(children: parseSnippet(item.snippet)),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 4),
          // 생성 일시
          Text(
            _formatDate(item.createdAt),
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[600],
            ),
          ),
        ],
      ),
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
    );
  }

  // 날짜 포맷 (yyyy.MM.dd HH:mm)
  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${local.year}.${local.month.toString().padLeft(2, '0')}.${local.day.toString().padLeft(2, '0')} '
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }

  // <b>태그를 볼드 TextSpan으로 변환하는 유틸리티 메서드
  // 예: "hello <b>world</b> foo" → [normal, bold, normal]
  static List<TextSpan> parseSnippet(String snippet) {
    final spans = <TextSpan>[];
    // <b>...</b> 패턴 분리
    final regex = RegExp(r'<b>(.*?)</b>');
    int lastEnd = 0;

    for (final match in regex.allMatches(snippet)) {
      // 볼드 이전 일반 텍스트
      if (match.start > lastEnd) {
        spans.add(TextSpan(text: snippet.substring(lastEnd, match.start)));
      }
      // 볼드 텍스트
      spans.add(
        TextSpan(
          text: match.group(1),
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
      );
      lastEnd = match.end;
    }

    // 마지막 일반 텍스트
    if (lastEnd < snippet.length) {
      spans.add(TextSpan(text: snippet.substring(lastEnd)));
    }

    // 태그 없으면 전체를 일반 텍스트로 반환
    if (spans.isEmpty) {
      spans.add(TextSpan(text: snippet));
    }

    return spans;
  }
}

// 필터 칩 위젯
class _FilterChip extends StatelessWidget {
  final String label;
  final VoidCallback? onDeleted;

  const _FilterChip({
    required this.label,
    this.onDeleted,
  });

  @override
  Widget build(BuildContext context) {
    return Chip(
      label: Text(
        label,
        style: const TextStyle(fontSize: 12),
      ),
      deleteIcon: onDeleted != null
          ? const Icon(Icons.close, size: 16)
          : null,
      onDeleted: onDeleted,
      backgroundColor: Theme.of(context).colorScheme.secondaryContainer,
      deleteIconColor: Theme.of(context).colorScheme.onSecondaryContainer,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      labelPadding: const EdgeInsets.symmetric(horizontal: 4),
    );
  }
}
