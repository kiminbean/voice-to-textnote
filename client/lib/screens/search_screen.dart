// 검색 화면 (SPEC-SEARCH-001)
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/search_result.dart';
import 'package:voice_to_textnote/providers/search_provider.dart';

// 검색 화면 - 회의록/요약 전문 검색
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

  // 현재 실제 검색에 사용 중인 쿼리
  String _activeQuery = '';

  @override
  void initState() {
    super.initState();
    // 텍스트 변경 감지
    _controller.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    // 타이머와 컨트롤러 정리
    _debounceTimer?.cancel();
    _controller.removeListener(_onTextChanged);
    _controller.dispose();
    super.dispose();
  }

  // 텍스트 변경 시 300ms 디바운스 후 검색 실행
  void _onTextChanged() {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 300), () {
      if (mounted) {
        setState(() {
          _activeQuery = _controller.text.trim();
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    // 현재 쿼리로 검색 결과 구독
    final searchQuery = SearchQuery(query: _activeQuery);
    final searchResult = ref.watch(searchResultProvider(searchQuery));

    return Scaffold(
      appBar: AppBar(
        // 뒤로가기 버튼 (기본 제공)
        leading: BackButton(onPressed: () => context.pop()),
        // 검색 입력 필드
        title: TextField(
          controller: _controller,
          autofocus: true, // 화면 진입 시 자동 포커스
          decoration: const InputDecoration(
            hintText: '검색어를 입력하세요',
            border: InputBorder.none,
          ),
          textInputAction: TextInputAction.search,
          style: const TextStyle(fontSize: 16),
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
      body: _buildBody(searchResult),
    );
  }

  // 검색 결과 본문 빌드
  Widget _buildBody(AsyncValue<SearchResponse> result) {
    // 검색어 없음: 안내 메시지
    if (_activeQuery.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text(
              '검색어를 2자 이상 입력하세요',
              style: TextStyle(color: Colors.grey, fontSize: 16),
            ),
          ],
        ),
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
                // 동일 쿼리로 재시도
                ref.invalidate(
                  searchResultProvider(SearchQuery(query: _activeQuery)),
                );
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
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text(
              '검색 결과가 없습니다',
              style: TextStyle(color: Colors.grey, fontSize: 16),
            ),
          ],
        ),
      );
    }

    // 검색 결과 목록
    return ListView.builder(
      itemCount: response.items.length,
      itemBuilder: (context, index) {
        final item = response.items[index];
        return _SearchResultTile(
          item: item,
          onTap: () => context.push('/result/${item.taskId}'),
        );
      },
    );
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
