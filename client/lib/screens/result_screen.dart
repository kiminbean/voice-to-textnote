// 결과 화면 - 실제 API 데이터 바인딩 + 에러/빈 상태
// SPEC-APP-003: 액션 아이템 표시, SPEC-APP-004: 주요 결정 사항/다음 단계 표시
// SPEC-EXPORT-001: PDF 내보내기 기능 추가
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import 'package:voice_to_textnote/models/action_item.dart';
import 'package:voice_to_textnote/models/meeting.dart';
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
      length: 4,
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
            isScrollable: true,
            tabs: [
              Tab(text: '회의 내용'),
              Tab(text: '회의록'),
              Tab(text: 'AI 요약'),
              Tab(text: '액션 아이템'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            // 회의 내용 탭: 화자별 원본 발화 세그먼트
            _TranscriptTab(taskId: minutesTaskId),
            // 회의록 탭: 양식 기반 테이블 형태 회의록
            _MinutesTab(taskId: summaryTaskId, meeting: meeting),
            // AI 요약 탭: 구조화된 분석 (주요 결정 사항 + 다음 단계)
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
        title: '회의 내용 준비 중',
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
            title: '회의 내용이 없습니다',
            subtitle: '처리가 완료되지 않았을 수 있습니다',
          );
        }

        // 회의록 텍스트를 세그먼트로 파싱하여 표시
        // MVP: 단일 텍스트 블록으로 표시
        return ListView(
          children: [
            SpeakerSegment(
              speakerName: '회의 내용',
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

// 회의록 탭: PDF 양식과 동일한 테이블 형태 회의록
class _MinutesTab extends ConsumerWidget {
  final String? taskId;
  final Meeting? meeting;

  const _MinutesTab({required this.taskId, this.meeting});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.description_outlined,
        title: '회의록 준비 중',
        subtitle: '처리가 완료되지 않았습니다',
      );
    }

    final summaryAsync = ref.watch(summaryResultProvider(taskId!));

    return summaryAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: '회의록을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(summaryResultProvider(taskId!)),
      ),
      data: (SummaryResult result) {
        if (result.summaryText.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.description_outlined,
            title: '회의록이 없습니다',
            subtitle: '양식을 선택하여 회의록을 생성해보세요',
          );
        }

        // REQ-UI-002: 양식 구조 있으면 동적 테이블, 없으면 기본 테이블
        if (result.sections.isNotEmpty) {
          return _buildDynamicTable(context, result);
        }
        return _buildMinutesTable(context, result);
      },
    );
  }

  // REQ-UI-002: 양식 테이블 레이아웃 기반 동적 테이블
  Widget _buildDynamicTable(BuildContext context, SummaryResult result) {
    final now = meeting?.createdAt ?? DateTime.now();
    final dateStr =
        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';

    const headerBg = Color(0xFFE3F2FD);
    const contentBg = Color(0xFFFFFDE7);
    final borderColor = Colors.grey.shade300;

    // template_structure에서 table_layout 추출
    final tableLayout = (result.templateStructure?['table_layout'] as List<dynamic>?) ?? [];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              '회의록_$dateStr',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
          ),
          Container(
            decoration: BoxDecoration(
              border: Border.all(color: borderColor),
            ),
            child: Column(
              children: tableLayout.isNotEmpty
                  ? _buildRowsFromLayout(tableLayout, result, headerBg, contentBg, borderColor)
                  // table_layout 없으면 sections 기반 단순 렌더링
                  : result.sections.entries.map((entry) {
                      final isLarge = entry.key.contains('내용') || entry.value.length > 100;
                      return _tableRow2Col(
                        entry.key, headerBg,
                        entry.value.isNotEmpty ? entry.value : '-',
                        isLarge ? contentBg : null,
                        borderColor,
                        minHeight: isLarge ? 150 : 0,
                      );
                    }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  // table_layout 기반 행 생성 (PDF 원본 행/열 구조 재현)
  List<Widget> _buildRowsFromLayout(
    List<dynamic> layout,
    SummaryResult result,
    Color headerBg,
    Color contentBg,
    Color borderColor,
  ) {
    final rows = <Widget>[];

    for (final rowDef in layout) {
      final type = rowDef['type'] as String? ?? 'full';

      if (type == 'split') {
        // 4열 행: 라벨1 | 내용1 | 라벨2 | 내용2
        final cells = (rowDef['cells'] as List<dynamic>?) ?? [];
        if (cells.length >= 2) {
          final label1 = cells[0]['label'] as String? ?? '';
          final label2 = cells[1]['label'] as String? ?? '';
          final value1 = result.sections[label1] ?? '-';
          final value2 = result.sections[label2] ?? '-';
          rows.add(_tableRow4Col(
            label1, headerBg, value1, null,
            label2, headerBg, value2, null,
            borderColor,
          ));
        }
      } else {
        // 2열 행: 라벨 | 내용
        final label = rowDef['label'] as String? ?? '';
        final value = result.sections[label] ?? '-';
        final isLarge = label.contains('내용') || label.contains('논의') || value.length > 100;
        rows.add(_tableRow2Col(
          label, headerBg,
          value.isNotEmpty ? value : '-',
          isLarge ? contentBg : null,
          borderColor,
          minHeight: isLarge ? 150 : 0,
        ));
      }
    }

    return rows;
  }

  // REQ-UI-004: 양식 미선택 시 기본 하드코딩 테이블
  Widget _buildMinutesTable(BuildContext context, SummaryResult result) {
    final now = meeting?.createdAt ?? DateTime.now();
    final dateStr =
        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    final timeStr =
        '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';

    const headerBg = Color(0xFFE3F2FD); // 연한 파란색 (라벨 셀)
    const contentBg = Color(0xFFFFFDE7); // 연한 노란색 (회의내용)
    const decisionBg = Color(0xFFFFFDE7); // 연한 노란색 (결정된 사안)
    final borderColor = Colors.grey.shade300;
    const courseName = '심화 ROS2와 AI를 이용한 자율주행&로봇팔 개발자 부트캠프';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 제목
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              '회의록_${now.year}${now.month.toString().padLeft(2, '0')}${now.day.toString().padLeft(2, '0')}',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
          ),
          // 테이블
          Container(
            decoration: BoxDecoration(
              border: Border.all(color: borderColor),
            ),
            child: Column(
              children: [
                // 1행: 과정명 (고정값)
                _tableRow2Col(
                  '과정명', headerBg,
                  courseName, null,
                  borderColor,
                ),
                // 2행: 프로젝트명 | 회의일시 (4열 구조)
                _tableRow4Col(
                  '프로젝트명', headerBg, meeting?.title ?? '-', null,
                  '회의일시', headerBg, '$dateStr $timeStr', null,
                  borderColor,
                ),
                // 3행: 팀명 | 작성자 (4열 구조)
                _tableRow4Col(
                  '팀명', headerBg, '-', null,
                  '작성자', headerBg, '-', null,
                  borderColor,
                ),
                // 4행: 참석자
                _tableRow2Col(
                  '참석자', headerBg,
                  '-', null,
                  borderColor,
                ),
                // 5행: 회의안건 (summaryText 첫 문장 추출)
                _tableRow2Col(
                  '회의안건', headerBg,
                  _extractAgenda(result.summaryText), null,
                  borderColor,
                ),
                // 6행: 회의내용 (큰 영역, 노란 배경)
                _tableRow2Col(
                  '회의내용', headerBg,
                  result.summaryText, contentBg,
                  borderColor,
                  minHeight: 200,
                ),
                // 7행: 결정된 사안
                _tableRow2Col(
                  '결정된 사안', headerBg,
                  result.keyDecisions.isNotEmpty
                      ? result.keyDecisions
                          .asMap()
                          .entries
                          .map((e) => '${e.key + 1}. ${e.value}')
                          .join('\n')
                      : '-',
                  decisionBg,
                  borderColor,
                  minHeight: 60,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // 2열 행: 라벨 | 내용 (전체 폭)
  Widget _tableRow2Col(
    String label, Color labelBg,
    String content, Color? contentBg,
    Color borderColor, {
    double minHeight = 0,
  }) {
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: borderColor)),
      ),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 라벨
            SizedBox(
              width: 90,
              child: Container(
                color: labelBg,
                padding: const EdgeInsets.all(10),
                alignment: Alignment.centerLeft,
                child: Text(
                  label,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
            Container(width: 1, color: borderColor),
            // 내용
            Expanded(
              child: Container(
                color: contentBg,
                padding: const EdgeInsets.all(10),
                constraints: BoxConstraints(minHeight: minHeight),
                child: Text(
                  content,
                  style: const TextStyle(height: 1.7, fontSize: 13),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 4열 행: 라벨1 | 내용1 | 라벨2 | 내용2
  Widget _tableRow4Col(
    String label1, Color labelBg1, String content1, Color? contentBg1,
    String label2, Color labelBg2, String content2, Color? contentBg2,
    Color borderColor,
  ) {
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: borderColor)),
      ),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 라벨1
            SizedBox(
              width: 90,
              child: Container(
                color: labelBg1,
                padding: const EdgeInsets.all(10),
                alignment: Alignment.centerLeft,
                child: Text(
                  label1,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
            Container(width: 1, color: borderColor),
            // 내용1
            Expanded(
              child: Container(
                color: contentBg1,
                padding: const EdgeInsets.all(10),
                child: Text(content1, style: const TextStyle(fontSize: 13)),
              ),
            ),
            Container(width: 1, color: borderColor),
            // 라벨2
            SizedBox(
              width: 70,
              child: Container(
                color: labelBg2,
                padding: const EdgeInsets.all(10),
                alignment: Alignment.centerLeft,
                child: Text(
                  label2,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
            Container(width: 1, color: borderColor),
            // 내용2
            Expanded(
              child: Container(
                color: contentBg2,
                padding: const EdgeInsets.all(10),
                child: Text(content2, style: const TextStyle(fontSize: 13)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 회의 요약에서 첫 문장을 회의안건으로 추출
  String _extractAgenda(String summaryText) {
    if (summaryText.isEmpty) return '-';
    // 마침표(.)로 끝나는 첫 문장 추출
    final dotIndex = summaryText.indexOf('.');
    if (dotIndex > 0 && dotIndex < 100) {
      return summaryText.substring(0, dotIndex + 1);
    }
    // 마침표가 없거나 너무 길면 80자로 자르기
    if (summaryText.length > 80) {
      return '${summaryText.substring(0, 80)}...';
    }
    return summaryText;
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
              ShimmerText(lines: 8),
            ],
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
