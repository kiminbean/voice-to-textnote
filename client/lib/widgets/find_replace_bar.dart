import 'package:flutter/material.dart';

class FindReplaceBar extends StatefulWidget {
  final String searchQuery;
  final ValueChanged<String> onSearchChanged;
  final VoidCallback onNext;
  final VoidCallback onPrevious;
  final VoidCallback onClose;
  final int matchCount;
  final int currentMatchIndex;

  const FindReplaceBar({
    super.key,
    required this.searchQuery,
    required this.onSearchChanged,
    required this.onNext,
    required this.onPrevious,
    required this.onClose,
    required this.matchCount,
    required this.currentMatchIndex,
  });

  @override
  State<FindReplaceBar> createState() => _FindReplaceBarState();
}

class _FindReplaceBarState extends State<FindReplaceBar> {
  late TextEditingController _searchController;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController(text: widget.searchQuery);
  }

  @override
  void didUpdateWidget(FindReplaceBar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.searchQuery != widget.searchQuery &&
        _searchController.text != widget.searchQuery) {
      _searchController.text = widget.searchQuery;
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      elevation: 4,
      color: theme.colorScheme.surface,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _searchController,
                decoration: InputDecoration(
                  hintText: '검색어 입력',
                  isDense: true,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
                onChanged: widget.onSearchChanged,
              ),
            ),
            const SizedBox(width: 8),
            if (widget.searchQuery.isNotEmpty)
              Text(
                widget.matchCount > 0
                    ? '${widget.currentMatchIndex + 1}/${widget.matchCount}'
                    : '0/0',
                style: theme.textTheme.bodySmall,
              ),
            IconButton(
              icon: const Icon(Icons.keyboard_arrow_up),
              onPressed: widget.matchCount > 0 ? widget.onPrevious : null,
              tooltip: '이전',
            ),
            IconButton(
              icon: const Icon(Icons.keyboard_arrow_down),
              onPressed: widget.matchCount > 0 ? widget.onNext : null,
              tooltip: '다음',
            ),
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: widget.onClose,
              tooltip: '닫기',
            ),
          ],
        ),
      ),
    );
  }
}
