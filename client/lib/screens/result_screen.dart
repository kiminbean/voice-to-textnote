// 결과 화면 - 실제 API 데이터 바인딩 + 에러/빈 상태
// SPEC-APP-003: 액션 아이템 표시, SPEC-APP-004: 주요 결정 사항/다음 단계 표시
// SPEC-EXPORT-001: PDF 내보내기 기능 추가
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import 'package:voice_to_textnote/models/action_item.dart';
import 'package:voice_to_textnote/models/summary_result.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/providers/result_provider.dart';
import 'package:voice_to_textnote/services/export_api.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';
import 'package:voice_to_textnote/widgets/error_retry_widget.dart';
import 'package:voice_to_textnote/widgets/shimmer_text.dart';
import 'package:voice_to_textnote/widgets/speaker_segment.dart';

// ConsumerStatefulWidget으로 변경: _isExporting 상태 관리 필요
class ResultScreen extends ConsumerStatefulWidget {
  final String meetingId;

  const ResultScreen({super.key, required this.meetingId});

  @override
  ConsumerState<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends ConsumerState<ResultScreen> {
  // PDF 내보내기 진행 중 여부 (중복 탭 방지)
  bool _isExporting = false;

  /// PDF 내보내기 및 공유 처리
  Future<void> _exportPdf(
    BuildContext context,
    String? minutesTaskId,
    String? summaryTaskId,
  ) async {
    // minutesTaskId 없으면 내보내기 불가
    if (minutesTaskId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('회의록 처리가 완료되지 않아 PDF를 내보낼 수 없습니다.')),
      );
      return;
    }

    // 중복 탭 방지
    if (_isExporting) return;
    setState(() => _isExporting = true);

    try {
      final exportApi = ref.read(exportApiProvider);
      final file = await exportApi.downloadPdf(
        minutesTaskId,
        summaryTaskId: summaryTaskId,
      );

      // share_plus로 파일 공유 (AirDrop, 이메일, 저장 등)
      await Share.shareXFiles(
        [XFile(file.path, mimeType: 'application/pdf')],
        subject: '회의록 PDF',
      );
    } catch (e) {
      // 위젯이 마운트된 경우에만 SnackBar 표시
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('PDF 내보내기 실패: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isExporting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Meeting에서 파이프라인 task ID 조회
    final meetings = ref.watch(meetingListProvider);
    final meeting = meetings.where((m) => m.id == widget.meetingId).firstOrNull;
    final minutesTaskId = meeting?.minutesTaskId;
    final summaryTaskId = meeting?.summaryTaskId;

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => Navigator.of(context).canPop()
                ? Navigator.of(context).pop()
                : context.go('/'),
          ),
          title: const Text('회의 결과'),
          // PDF 내보내기 버튼 추가
          actions: [
            _isExporting
                ? const Padding(
                    padding: EdgeInsets.all(14),
                    child: SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : IconButton(
                    icon: const Icon(Icons.picture_as_pdf_outlined),
                    tooltip: 'PDF 내보내기',
                    onPressed: () =>
                        _exportPdf(context, minutesTaskId, summaryTaskId),
                  ),
          ],
          bottom: const TabBar(
            tabs: [
              Tab(text: '회의록'),
              Tab(text: 'AI 요약'),
              Tab(text: '액션 아이템'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            // 회의록 탭 (minutesTaskId 사용)
            _TranscriptTab(taskId: minutesTaskId),
            // AI 요약 탭 (summaryTaskId 사용)
            _SummaryTab(taskId: summaryTaskId),
            // 액션 아이템 탭 (summaryTaskId 사용)
            _ActionItemsTab(taskId: summaryTaskId),
          ],
        ),
      ),
    );
  }
}

// 회의록 탭
class _TranscriptTab extends ConsumerWidget {
  final String? taskId;

  const _TranscriptTab({required this.taskId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // task ID가 없으면 빈 상태 표시
    if (taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.article_outlined,
        title: '회의록 준비 중',
        subtitle: '처리가 완료되지 않았습니다',
      );
    }

    final minutesAsync = ref.watch(minutesResultProvider(taskId!));

    return minutesAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: '회의록을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(minutesResultProvider(taskId!)),
      ),
      data: (minutes) {
        if (minutes.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.article_outlined,
            title: '회의록이 없습니다',
            subtitle: '처리가 완료되지 않았을 수 있습니다',
          );
        }

        // 회의록 텍스트를 세그먼트로 파싱하여 표시
        // MVP: 단일 텍스트 블록으로 표시
        return ListView(
          children: [
            SpeakerSegment(
              speakerName: '회의록',
              text: minutes,
              startTime: Duration.zero,
              speakerIndex: 0,
            ),
          ],
        );
      },
    );
  }

  // shimmer 로딩 스켈레톤
  Widget _buildShimmerLoading() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: List.generate(
          4,
          (_) => const Padding(
            padding: EdgeInsets.only(bottom: 16),
            child: ShimmerText(lines: 4),
          ),
        ),
      ),
    );
  }
}

// AI 요약 탭
class _SummaryTab extends ConsumerWidget {
  final String? taskId;

  const _SummaryTab({required this.taskId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // task ID가 없으면 빈 상태 표시
    if (taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.summarize_outlined,
        title: 'AI 요약 준비 중',
        subtitle: '처리가 완료되지 않았습니다',
      );
    }

    final summaryAsync = ref.watch(summaryResultProvider(taskId!));

    return summaryAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: 'AI 요약을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(summaryResultProvider(taskId!)),
      ),
      data: (SummaryResult result) {
        if (result.summaryText.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.summarize_outlined,
            title: 'AI 요약이 없습니다',
          );
        }

        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'AI 요약',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const Divider(),
                  Text(
                    result.summaryText,
                    style: const TextStyle(height: 1.6),
                  ),
                  // 주요 결정 사항 섹션 (SPEC-APP-004 REQ-APP-042)
                  if (result.keyDecisions.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Text(
                      '주요 결정 사항',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const Divider(),
                    ...result.keyDecisions.asMap().entries.map((e) =>
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text(
                          '${e.key + 1}. ${e.value}',
                          style: const TextStyle(height: 1.6),
                        ),
                      ),
                    ),
                  ],
                  // 다음 단계 섹션 (SPEC-APP-004 REQ-APP-043)
                  if (result.nextSteps.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Text(
                      '다음 단계',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const Divider(),
                    ...result.nextSteps.asMap().entries.map((e) =>
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text(
                          '${e.key + 1}. ${e.value}',
                          style: const TextStyle(height: 1.6),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildShimmerLoading() {
    return const Padding(
      padding: EdgeInsets.all(16),
      child: Card(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ShimmerText(lines: 1),
              SizedBox(height: 16),
              Divider(),
              SizedBox(height: 8),
              ShimmerText(lines: 5),
            ],
          ),
        ),
      ),
    );
  }
}

// 우선순위 배지 색상 상수 (SPEC-APP-003 REQ-APP-033)
const _priorityColors = {
  'high': Colors.red,
  'medium': Colors.orange,
  'low': Colors.green,
};

// 액션 아이템 탭 - ConsumerStatefulWidget으로 필터 상태 관리
// @MX:ANCHOR: _ActionItemsTab은 summaryResultProvider를 통해 액션 아이템을 렌더링
// @MX:REASON: result_screen의 핵심 UI 진입점, 필터 상태와 API 데이터 결합
class _ActionItemsTab extends ConsumerStatefulWidget {
  final String? taskId;

  const _ActionItemsTab({required this.taskId});

  @override
  ConsumerState<_ActionItemsTab> createState() => _ActionItemsTabState();
}

class _ActionItemsTabState extends ConsumerState<_ActionItemsTab> {
  // 현재 선택된 우선순위 필터 (null = 전체)
  String? _selectedPriority;

  @override
  Widget build(BuildContext context) {
    // task ID가 없으면 빈 상태 표시
    if (widget.taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.checklist_outlined,
        title: '액션 아이템 준비 중',
        subtitle: '처리가 완료되지 않았습니다',
      );
    }

    final summaryAsync = ref.watch(summaryResultProvider(widget.taskId!));

    return summaryAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: '액션 아이템을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(summaryResultProvider(widget.taskId!)),
      ),
      data: (SummaryResult result) {
        // SummaryResult에서 타입 안전하게 액션 아이템 조회 (SPEC-APP-004 REQ-APP-041)
        final allItems = result.actionItems;

        if (allItems.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.checklist_outlined,
            title: '액션 아이템이 없습니다',
          );
        }

        // 필터 적용 (SPEC-APP-003 REQ-APP-034)
        final filteredItems = _selectedPriority == null
            ? allItems
            : allItems
                .where((item) => item.priority == _selectedPriority)
                .toList();

        return Column(
          children: [
            // 우선순위 필터 칩 행
            _buildFilterRow(),
            // 액션 아이템 카드 목록
            Expanded(
              child: _ActionItemCardList(items: filteredItems),
            ),
          ],
        );
      },
    );
  }

  // 우선순위 필터 칩 행 (SPEC-APP-003 REQ-APP-034)
  Widget _buildFilterRow() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          // 전체 필터
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              label: const Text('전체'),
              selected: _selectedPriority == null,
              onSelected: (_) => setState(() => _selectedPriority = null),
            ),
          ),
          // High 필터
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              label: const Text('High'),
              selected: _selectedPriority == 'high',
              onSelected: (_) => setState(() => _selectedPriority = 'high'),
            ),
          ),
          // Medium 필터
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              label: const Text('Medium'),
              selected: _selectedPriority == 'medium',
              onSelected: (_) => setState(() => _selectedPriority = 'medium'),
            ),
          ),
          // Low 필터
          FilterChip(
            label: const Text('Low'),
            selected: _selectedPriority == 'low',
            onSelected: (_) => setState(() => _selectedPriority = 'low'),
          ),
        ],
      ),
    );
  }

  Widget _buildShimmerLoading() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: List.generate(
          3,
          (_) => const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: ShimmerText(lines: 1),
          ),
        ),
      ),
    );
  }
}

// 액션 아이템 리치 카드 목록 (SPEC-APP-003 REQ-APP-032)
class _ActionItemCardList extends StatefulWidget {
  final List<ActionItem> items;

  const _ActionItemCardList({required this.items});

  @override
  State<_ActionItemCardList> createState() => _ActionItemCardListState();
}

class _ActionItemCardListState extends State<_ActionItemCardList> {
  // 각 아이템의 체크 상태
  late List<bool> _checked;

  @override
  void initState() {
    super.initState();
    _checked = List.filled(widget.items.length, false);
  }

  @override
  void didUpdateWidget(_ActionItemCardList oldWidget) {
    super.didUpdateWidget(oldWidget);
    // 아이템 목록이 바뀌면 체크 상태 초기화
    if (oldWidget.items.length != widget.items.length) {
      _checked = List.filled(widget.items.length, false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: widget.items.length,
      itemBuilder: (context, index) {
        final item = widget.items[index];
        final done = _checked[index];
        final priorityColor =
            _priorityColors[item.priority] ?? Colors.orange;

        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: CheckboxListTile(
            value: done,
            // 작업 내용 (완료 시 취소선)
            title: Text(
              item.task,
              style: TextStyle(
                decoration: done ? TextDecoration.lineThrough : null,
                color: done ? Colors.grey : null,
              ),
            ),
            // 담당자 + 마감일 표시
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('담당자: ${item.assignee ?? '미지정'}'),
                if (item.deadline != null)
                  Text('마감: ${item.deadline}'),
              ],
            ),
            // 우선순위 배지
            secondary: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: priorityColor,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                item.priority.toUpperCase(),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            onChanged: (value) {
              setState(() {
                _checked[index] = value ?? false;
              });
            },
          ),
        );
      },
    );
  }
}
