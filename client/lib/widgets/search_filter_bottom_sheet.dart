// 검색 필터 bottom sheet 위젯 (SPEC-SEARCH-002 Phase 4)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/search_result.dart';
import 'package:voice_to_textnote/providers/search_provider.dart';

// 검색 필터 bottom sheet
class SearchFilterBottomSheet extends ConsumerStatefulWidget {
  // 현재 필터 상태
  final SearchFilterState initialFilter;

  const SearchFilterBottomSheet({
    super.key,
    required this.initialFilter,
  });

  @override
  ConsumerState<SearchFilterBottomSheet> createState() =>
      _SearchFilterBottomSheetState();
}

class _SearchFilterBottomSheetState
    extends ConsumerState<SearchFilterBottomSheet> {
  // 정렬 순서
  late String _sort;
  // 시작 날짜
  DateTime? _dateFrom;
  // 종료 날짜
  DateTime? _dateTo;
  // 발언자
  late TextEditingController _speakerController;
  // 행동 항목 필터
  bool? _hasActionItems;
  // 핵심 결정 사항 필터
  bool? _hasKeyDecisions;

  @override
  void initState() {
    super.initState();
    _sort = widget.initialFilter.sort ?? 'relevance';

    // 날짜 파싱
    if (widget.initialFilter.dateFrom != null) {
      try {
        _dateFrom = DateTime.parse(widget.initialFilter.dateFrom!);
      } catch (e) {
        // 무시
      }
    }

    if (widget.initialFilter.dateTo != null) {
      try {
        _dateTo = DateTime.parse(widget.initialFilter.dateTo!);
      } catch (e) {
        // 무시
      }
    }

    _speakerController = TextEditingController(text: widget.initialFilter.speaker ?? '');
    _hasActionItems = widget.initialFilter.hasActionItems;
    _hasKeyDecisions = widget.initialFilter.hasKeyDecisions;
  }

  @override
  void dispose() {
    _speakerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 헤더
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                '검색 필터',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                ),
              ),
              // 필터 초기화 버튼
              TextButton(
                onPressed: _resetFilters,
                child: const Text('초기화'),
              ),
            ],
          ),
          const Divider(),
          const SizedBox(height: 16),

          // 정렬 순서
          _buildSortDropdown(),
          const SizedBox(height: 16),

          // 날짜 범위
          _buildDateRangePicker(),
          const SizedBox(height: 16),

          // 발언자
          _buildSpeakerField(),
          const SizedBox(height: 16),

          // 행동 항목 토글
          _buildActionItemsToggle(),
          const SizedBox(height: 8),

          // 핵심 결정 사항 토글
          _buildKeyDecisionsToggle(),
          const SizedBox(height: 24),

          // 적용 버튼
          ElevatedButton(
            onPressed: _applyFilters,
            child: const Text('필터 적용'),
          ),
        ],
      ),
    );
  }

  // 정렬 순서 드롭다운
  Widget _buildSortDropdown() {
    return DropdownButtonFormField<String>(
      value: _sort,
      decoration: const InputDecoration(
        labelText: '정렬 순서',
        border: OutlineInputBorder(),
      ),
      items: const [
        DropdownMenuItem(value: 'relevance', child: Text('관련도순')),
        DropdownMenuItem(value: 'newest', child: Text('최신순')),
        DropdownMenuItem(value: 'oldest', child: Text('오래된순')),
      ],
      onChanged: (value) {
        setState(() {
          _sort = value ?? 'relevance';
        });
      },
    );
  }

  // 날짜 범위 선택기
  Widget _buildDateRangePicker() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '날짜 범위',
          style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => _selectDate(from: true),
                icon: const Icon(Icons.calendar_today, size: 18),
                label: Text(
                  _dateFrom != null
                      ? '${_dateFrom!.year}.${_dateFrom!.month}.${_dateFrom!.day}'
                      : '시작일',
                ),
              ),
            ),
            const SizedBox(width: 8),
            const Text('~'),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => _selectDate(from: false),
                icon: const Icon(Icons.calendar_today, size: 18),
                label: Text(
                  _dateTo != null
                      ? '${_dateTo!.year}.${_dateTo!.month}.${_dateTo!.day}'
                      : '종료일',
                ),
              ),
            ),
          ],
        ),
        if (_dateFrom != null || _dateTo != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: TextButton(
              onPressed: _clearDateRange,
              child: const Text('날짜 범위 초기화'),
            ),
          ),
      ],
    );
  }

  // 발언자 입력 필드
  Widget _buildSpeakerField() {
    return TextField(
      controller: _speakerController,
      decoration: const InputDecoration(
        labelText: '발언자 이름',
        hintText: '발언자 이름으로 필터',
        border: OutlineInputBorder(),
      ),
    );
  }

  // 행동 항목 토글 스위치
  Widget _buildActionItemsToggle() {
    return SwitchListTile(
      title: const Text('행동 항목 포함'),
      subtitle: const Text(
        '행동 항목이 있는 결과만 표시',
        style: TextStyle(fontSize: 12),
      ),
      value: _hasActionItems ?? false,
      onChanged: (value) {
        setState(() {
          _hasActionItems = value ? true : null;
        });
      },
    );
  }

  // 핵심 결정 사항 토글 스위치
  Widget _buildKeyDecisionsToggle() {
    return SwitchListTile(
      title: const Text('핵심 결정 사항 포함'),
      subtitle: const Text(
        '핵심 결정 사항이 있는 결과만 표시',
        style: TextStyle(fontSize: 12),
      ),
      value: _hasKeyDecisions ?? false,
      onChanged: (value) {
        setState(() {
          _hasKeyDecisions = value ? true : null;
        });
      },
    );
  }

  // 날짜 선택
  Future<void> _selectDate({required bool from}) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: from
          ? _dateFrom ?? DateTime.now()
          : _dateTo ?? DateTime.now(),
      firstDate: DateTime(2020),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );

    if (picked != null) {
      setState(() {
        if (from) {
          _dateFrom = picked;
        } else {
          _dateTo = picked;
        }
      });
    }
  }

  // 날짜 범위 초기화
  void _clearDateRange() {
    setState(() {
      _dateFrom = null;
      _dateTo = null;
    });
  }

  // 모든 필터 초기화
  void _resetFilters() {
    setState(() {
      _sort = 'relevance';
      _dateFrom = null;
      _dateTo = null;
      _speakerController.clear();
      _hasActionItems = null;
      _hasKeyDecisions = null;
    });
  }

  // 필터 적용
  void _applyFilters() {
    final newFilter = SearchFilterState(
      sort: _sort,
      dateFrom: _dateFrom?.toIso8601String().split('T')[0],
      dateTo: _dateTo?.toIso8601String().split('T')[0],
      speaker: _speakerController.text.trim().isEmpty
          ? null
          : _speakerController.text.trim(),
      hasActionItems: _hasActionItems,
      hasKeyDecisions: _hasKeyDecisions,
    );

    ref.read(searchFilterProvider.notifier).state = newFilter;
    Navigator.of(context).pop(newFilter);
  }
}
