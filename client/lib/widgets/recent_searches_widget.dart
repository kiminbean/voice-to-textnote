// 최근 검색어 위젯 (SPEC-SEARCH-002 Phase 5)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

// 최근 검색어 Provider (SharedPreferences 기반, search_provider.dart에서 정의)
// 여기서는 provider를 주입받아 사용

/// 최근 검색어 위젯
class RecentSearchesWidget extends ConsumerWidget {
  /// 최근 검색어 목록 Provider
  final StateProvider<List<String>> recentSearchesProvider;

  /// 검색어 선택 콜백
  final ValueChanged<String> onSearch;

  const RecentSearchesWidget({
    super.key,
    required this.recentSearchesProvider,
    required this.onSearch,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recentSearches = ref.watch(recentSearchesProvider);

    // 최근 검색어 없음
    if (recentSearches.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 헤더
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                '최근 검색어',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey,
                ),
              ),
              // 전체 삭제 버튼
              TextButton(
                onPressed: () {
                  ref.read(recentSearchesProvider.notifier).state = [];
                },
                child: const Text(
                  '전체 삭제',
                  style: TextStyle(fontSize: 12),
                ),
              ),
            ],
          ),
        ),
        // 최근 검색어 목록 (칩 형태)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: recentSearches.map((query) {
              return _RecentSearchChip(
                query: query,
                onTap: () => onSearch(query),
                onDelete: () {
                  final current = ref.read(recentSearchesProvider);
                  ref.read(recentSearchesProvider.notifier).state =
                      current.where((q) => q != query).toList();
                },
              );
            }).toList(),
          ),
        ),
        const Divider(height: 32),
      ],
    );
  }
}

/// 개별 최근 검색어 칩
class _RecentSearchChip extends StatelessWidget {
  final String query;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  const _RecentSearchChip({
    required this.query,
    required this.onTap,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Chip(
        label: Text(
          query,
          style: const TextStyle(fontSize: 13),
        ),
        onDeleted: onDelete,
        deleteIcon: const Icon(Icons.close, size: 16),
        deleteIconColor: Colors.grey[600],
        backgroundColor: Colors.grey[200],
        labelPadding: const EdgeInsets.symmetric(horizontal: 8),
        padding: const EdgeInsets.symmetric(horizontal: 4),
        avatar: const Icon(
          Icons.history,
          size: 16,
          color: Colors.grey,
        ),
      ),
    );
  }
}
