// 결과 화면 - 실제 API 데이터 바인딩 + 에러/빈 상태
// SPEC-APP-003: 액션 아이템 표시, SPEC-APP-004: 주요 결정 사항/다음 단계 표시
// SPEC-EXPORT-001: PDF 내보내기 기능 추가
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import 'package:voice_to_textnote/models/action_item.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/models/mind_map_result.dart';
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

    // iOS 공유 팝오버 위치 (async 전에 캡처)
    final box = context.findRenderObject() as RenderBox?;
    final shareOrigin = box != null
        ? box.localToGlobal(Offset.zero) & box.size
        : const Rect.fromLTWH(0, 0, 100, 100);

    try {
      final exportApi = ref.read(exportApiProvider);
      final file = await exportApi.downloadPdf(
        minutesTaskId,
        summaryTaskId: summaryTaskId,
      );
      await Share.shareXFiles(
        [XFile(file.path, mimeType: 'application/pdf')],
        subject: '회의록 PDF',
        sharePositionOrigin: shareOrigin,
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
    // Meeting에서 파이프라인 task ID 조회 (AsyncNotifier이므로 .value 사용)
    final meetings = ref.watch(meetingListProvider).value ?? [];
    final meeting = meetings.where((m) => m.id == widget.meetingId).firstOrNull;
    final minutesTaskId = meeting?.minutesTaskId;
    final summaryTaskId = meeting?.summaryTaskId;

    return DefaultTabController(
      length: 5,
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
              Tab(text: '마인드맵'),
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
            // 마인드맵 탭: 백엔드 AI 생성 API 기반 관계 그래프
            _MindMapTab(taskId: summaryTaskId),
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

// 회의록 탭: PDF 양식과 동일한 테이블 형태 회의록 + 편집 기능
class _MinutesTab extends ConsumerStatefulWidget {
  final String? taskId;
  final Meeting? meeting;

  const _MinutesTab({required this.taskId, this.meeting});

  @override
  ConsumerState<_MinutesTab> createState() => _MinutesTabState();
}

class _MinutesTabState extends ConsumerState<_MinutesTab> {
  // 편집된 섹션 값 (원본 데이터 위에 오버레이)
  final Map<String, String> _editedSections = {};
  bool _isEditing = false;

  Meeting? get meeting => widget.meeting;
  String? get taskId => widget.taskId;

  @override
  Widget build(BuildContext context) {
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
        return Column(
          children: [
            // 편집 버튼
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton.icon(
                    onPressed: () => setState(() => _isEditing = !_isEditing),
                    icon: Icon(_isEditing ? Icons.check : Icons.edit, size: 18),
                    label: Text(_isEditing ? '편집 완료' : '편집'),
                  ),
                ],
              ),
            ),
            // 편집 모드 시각적 피드백
            if (_isEditing)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Text(
                  '📌 편집할 셀을 탭하세요',
                  style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.primary),
                ),
              ),
            // 테이블
            Expanded(
              child: result.sections.isNotEmpty
                  ? _buildDynamicTable(context, result)
                  : _buildMinutesTable(context, result),
            ),
          ],
        );
      },
    );
  }

  // REQ-UI-002: 양식 테이블 레이아웃 기반 동적 테이블
  Widget _buildDynamicTable(BuildContext context, SummaryResult result) {
    final now = meeting?.createdAt ?? DateTime.now();
    final dateStr =
        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';

    final theme = Theme.of(context);
    final headerBg = theme.colorScheme.primaryContainer.withAlpha(60);
    final contentBg = theme.colorScheme.secondaryContainer.withAlpha(40);
    final borderColor = theme.dividerColor;

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
                      final value = entry.value.isNotEmpty ? entry.value : '-';
                      final row = _tableRow2Col(
                        entry.key, headerBg,
                        value,
                        isLarge ? contentBg : null,
                        borderColor,
                        minHeight: isLarge ? 150 : 0,
                      );
                      return _isEditing
                          ? GestureDetector(
                              onTap: () => _editCell(entry.key, value == '-' ? '' : value),
                              child: row,
                            )
                          : row;
                    }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  // 편집 모드에서 split 행의 각 셀을 개별적으로 편집 가능하도록 래핑
  Widget _wrapSplitRowWithEdit(
    List<dynamic> cells,
    SummaryResult result,
    Color headerBg,
    Color contentBg,
    Color borderColor,
  ) {
    if (cells.length == 2) {
      final label1 = cells[0]['label'] as String? ?? '';
      final label2 = cells[1]['label'] as String? ?? '';
      final value1 = _resolveValue(label1, result);
      final value2 = _resolveValue(label2, result);
      final theme = Theme.of(context);
      final editBorder = theme.colorScheme.primary.withAlpha(100);

      return Container(
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: borderColor)),
        ),
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 셀 1
              SizedBox(
                width: 90,
                child: Container(
                  color: headerBg,
                  padding: const EdgeInsets.all(10),
                  alignment: Alignment.centerLeft,
                  child: Text(label1, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: theme.colorScheme.onSurface), maxLines: 2, overflow: TextOverflow.ellipsis),
                ),
              ),
              Container(width: 1, color: borderColor),
              Expanded(
                child: GestureDetector(
                  onTap: () => _editCell(label1, value1),
                  child: Container(
                    decoration: BoxDecoration(border: Border.all(color: editBorder, width: 1)),
                    padding: const EdgeInsets.all(10),
                    child: Text(value1, style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface), softWrap: true),
                  ),
                ),
              ),
              Container(width: 1, color: borderColor),
              // 셀 2
              SizedBox(
                width: 70,
                child: Container(
                  color: headerBg,
                  padding: const EdgeInsets.all(10),
                  alignment: Alignment.centerLeft,
                  child: Text(label2, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: theme.colorScheme.onSurface), maxLines: 2, overflow: TextOverflow.ellipsis),
                ),
              ),
              Container(width: 1, color: borderColor),
              Expanded(
                child: GestureDetector(
                  onTap: () => _editCell(label2, value2),
                  child: Container(
                    decoration: BoxDecoration(border: Border.all(color: editBorder, width: 1)),
                    padding: const EdgeInsets.all(10),
                    child: Text(value2, style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface), softWrap: true),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }
    // 3+ 셀: 단순 N열 레이아웃
    final labels = cells.map((c) => c['label'] as String? ?? '').toList();
    final values = labels.map((l) => _resolveValue(l, result)).toList();
    final row = _tableRowNCol(labels, values, headerBg, borderColor);
    return GestureDetector(
      onTap: () => _editCell(labels.first, values.first),
      child: row,
    );
  }

  // 특정 라벨에 대해 고정값 반환 (과정명, 미팅시간 등)
  // 편집된 값이 있으면 편집값 우선 사용
  String _resolveValue(String label, SummaryResult result) {
    // 편집된 값 우선
    if (_editedSections.containsKey(label)) return _editedSections[label]!;

    const courseName = '심화 ROS2와 AI를 이용한 자율주행&로봇팔 개발자 부트캠프';
    final now = meeting?.createdAt ?? DateTime.now();
    final dateTimeStr =
        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')} '
        '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';

    if (label == '과정명') return courseName;
    if (label == '미팅시간' || label == '회의일시') return dateTimeStr;
    return result.sections[label] ?? '-';
  }

  // 셀 편집 다이얼로그
  // @MX:NOTE: TextEditingController 메모리 누수 방지를 위해 finally에서 dispose 호출
  Future<void> _editCell(String label, String currentValue) async {
    final controller = TextEditingController(text: currentValue);
    try {
      final newValue = await showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(label),
          content: TextField(
            controller: controller,
            maxLines: label.contains('내용') || label.contains('이슈') ? 8 : 2,
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, controller.text),
              child: const Text('저장'),
            ),
          ],
        ),
      );
      // async gap 후 mounted 체크 (위젯이 dispose된 경우 setState 방지)
      if (newValue != null && mounted) {
        setState(() => _editedSections[label] = newValue);
      }
    } catch (e) {
      // 다이얼로그 오류 시 사용자에게 알림 (위젯이 살아있을 때만)
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('편집 중 오류가 발생했습니다: $e')),
        );
      }
    } finally {
      controller.dispose();
    }
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
        final cells = (rowDef['cells'] as List<dynamic>?) ?? [];
        Widget splitRow;
        if (cells.length == 2) {
          final label1 = cells[0]['label'] as String? ?? '';
          final label2 = cells[1]['label'] as String? ?? '';
          final value1 = _resolveValue(label1, result);
          final value2 = _resolveValue(label2, result);
          splitRow = _tableRow4Col(
            label1, headerBg, value1, null,
            label2, headerBg, value2, null,
            borderColor,
          );
        } else {
          final labels = cells.map((c) => c['label'] as String? ?? '').toList();
          splitRow = _tableRowNCol(
            labels,
            labels.map((l) => _resolveValue(l, result)).toList(),
            headerBg, borderColor,
          );
        }
        // 편집 모드 - split 행의 첫 번째 라벨로 편집 다이얼로그
        if (_isEditing) {
          // 편집 모드: 각 셀을 개별적으로 편집 가능하도록 IntrinsicHeight Row 내부에 GestureDetector 삽입
          rows.add(_wrapSplitRowWithEdit(cells, result, headerBg, contentBg, borderColor));
        } else {
          rows.add(splitRow);
        }
      } else {
        final label = rowDef['label'] as String? ?? '';
        final value = _resolveValue(label, result);
        final isLarge = label.contains('내용') || label.contains('논의') || label.contains('이슈') || value.length > 100;
        final row = _tableRow2Col(
          label, headerBg,
          value.isNotEmpty ? value : '-',
          isLarge ? contentBg : null,
          borderColor,
          minHeight: isLarge ? 150 : 0,
        );
        // 편집 모드일 때 탭하면 편집 다이얼로그
        rows.add(_isEditing
            ? GestureDetector(
                onTap: () => _editCell(label, value == '-' ? '' : value),
                child: row,
              )
            : row);
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

    final theme = Theme.of(context);
    final headerBg = theme.colorScheme.primaryContainer.withAlpha(60);
    final contentBg = theme.colorScheme.secondaryContainer.withAlpha(40);
    final decisionBg = theme.colorScheme.tertiaryContainer.withAlpha(40);
    final borderColor = theme.dividerColor;
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
                _wrapEditRow('과정명', courseName, headerBg, null, borderColor),
                // 2행: 프로젝트명 | 회의일시 (4열 구조)
                _wrapEditSplitRow(
                  '프로젝트명', headerBg, meeting?.title ?? '-', null,
                  '회의일시', headerBg, '$dateStr $timeStr', null,
                  borderColor,
                ),
                // 3행: 팀명 | 작성자 (4열 구조)
                _wrapEditSplitRow(
                  '팀명', headerBg, '-', null,
                  '작성자', headerBg, '-', null,
                  borderColor,
                ),
                // 4행: 참석자
                _wrapEditRow('참석자', '-', headerBg, null, borderColor),
                // 5행: 회의안건 (summaryText 첫 문장 추출)
                _wrapEditRow('회의안건', _extractAgenda(result.summaryText), headerBg, null, borderColor),
                // 6행: 회의내용 (큰 영역, 노란 배경)
                _wrapEditRow('회의내용', result.summaryText, headerBg, contentBg, borderColor, minHeight: 200),
                // 7행: 결정된 사안
                _wrapEditRow(
                  '결정된 사안',
                  result.keyDecisions.isNotEmpty
                      ? result.keyDecisions
                          .asMap()
                          .entries
                          .map((e) => '${e.key + 1}. ${e.value}')
                          .join('\n')
                      : '-',
                  decisionBg,
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

  // 편집 모드 래핑: 2열 행
  Widget _wrapEditRow(String label, String value, Color labelBg, Color? contentBg, Color borderColor, {double minHeight = 0}) {
    final displayValue = _editedSections.containsKey(label) ? _editedSections[label]! : value;
    final row = _tableRow2Col(label, labelBg, displayValue.isEmpty ? '-' : displayValue, contentBg, borderColor, minHeight: minHeight);
    if (!_isEditing) return row;
    final theme = Theme.of(context);
    return GestureDetector(
      onTap: () => _editCell(label, displayValue == '-' ? '' : displayValue),
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(color: theme.colorScheme.primary.withAlpha(80), width: 1),
        ),
        child: row,
      ),
    );
  }

  // 편집 모드 래핑: 4열 split 행 — 각 셀 개별 편집
  Widget _wrapEditSplitRow(
    String label1, Color labelBg1, String content1, Color? contentBg1,
    String label2, Color labelBg2, String content2, Color? contentBg2,
    Color borderColor,
  ) {
    final displayVal1 = _editedSections.containsKey(label1) ? _editedSections[label1]! : content1;
    final displayVal2 = _editedSections.containsKey(label2) ? _editedSections[label2]! : content2;

    if (!_isEditing) {
      return _tableRow4Col(label1, labelBg1, displayVal1, contentBg1, label2, labelBg2, displayVal2, contentBg2, borderColor);
    }

    final theme = Theme.of(context);
    final editBorder = theme.colorScheme.primary.withAlpha(100);
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: borderColor)),
      ),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: 90,
              child: Container(
                color: labelBg1,
                padding: const EdgeInsets.all(10),
                alignment: Alignment.centerLeft,
                child: Text(label1, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: theme.colorScheme.onSurface), maxLines: 2, overflow: TextOverflow.ellipsis),
              ),
            ),
            Container(width: 1, color: borderColor),
            Expanded(
              child: GestureDetector(
                onTap: () => _editCell(label1, displayVal1 == '-' ? '' : displayVal1),
                child: Container(
                  decoration: BoxDecoration(border: Border.all(color: editBorder, width: 1)),
                  padding: const EdgeInsets.all(10),
                  child: Text(displayVal1, style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface), softWrap: true),
                ),
              ),
            ),
            Container(width: 1, color: borderColor),
            SizedBox(
              width: 70,
              child: Container(
                color: labelBg2,
                padding: const EdgeInsets.all(10),
                alignment: Alignment.centerLeft,
                child: Text(label2, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: theme.colorScheme.onSurface), maxLines: 2, overflow: TextOverflow.ellipsis),
              ),
            ),
            Container(width: 1, color: borderColor),
            Expanded(
              child: GestureDetector(
                onTap: () => _editCell(label2, displayVal2 == '-' ? '' : displayVal2),
                child: Container(
                  decoration: BoxDecoration(border: Border.all(color: editBorder, width: 1)),
                  padding: const EdgeInsets.all(10),
                  child: Text(displayVal2, style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface), softWrap: true),
                ),
              ),
            ),
          ],
        ),
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
    final theme = Theme.of(context);
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
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: theme.colorScheme.onSurface,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
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
                  style: TextStyle(height: 1.7, fontSize: 13, color: theme.colorScheme.onSurface),
                  softWrap: true,
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
    final theme = Theme.of(context);
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
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: theme.colorScheme.onSurface,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
            Container(width: 1, color: borderColor),
            // 내용1
            Expanded(
              child: Container(
                color: contentBg1,
                padding: const EdgeInsets.all(10),
                child: Text(
                  content1,
                  style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface),
                  softWrap: true,
                ),
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
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: theme.colorScheme.onSurface,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
            Container(width: 1, color: borderColor),
            // 내용2
            Expanded(
              child: Container(
                color: contentBg2,
                padding: const EdgeInsets.all(10),
                child: Text(
                  content2,
                  style: TextStyle(fontSize: 13, color: theme.colorScheme.onSurface),
                  softWrap: true,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // N열 동적 행: 라벨1 | 내용1 | 라벨2 | 내용2 | ... (균등 분할)
  Widget _tableRowNCol(
    List<String> labels,
    List<String> values,
    Color headerBg,
    Color borderColor,
  ) {
    final theme = Theme.of(context);
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: borderColor)),
      ),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (int i = 0; i < labels.length; i++) ...[
              // 라벨
              SizedBox(
                width: 70,
                child: Container(
                  color: headerBg,
                  padding: const EdgeInsets.all(8),
                  alignment: Alignment.centerLeft,
                  child: Text(
                    labels[i],
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: theme.colorScheme.onSurface),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ),
              Container(width: 1, color: borderColor),
              // 내용
              Expanded(
                child: Container(
                  padding: const EdgeInsets.all(8),
                  child: Text(
                    values[i],
                    style: TextStyle(fontSize: 11, color: theme.colorScheme.onSurface),
                    softWrap: true,
                  ),
                ),
              ),
              if (i < labels.length - 1) Container(width: 1, color: borderColor),
            ],
          ],
        ),
      ),
    );
  }

  // 회의 요약에서 첫 문장을 회의안건으로 추출
  // JSON 주석 안전 제거 (문자열 내부 // 보호, 문자 단위 추적)
  static String _safeStripComments(String text) {
    final lines = text.split('\n');
    final result = <String>[];
    for (var line in lines) {
      var inString = false;
      var strippedLine = line;
      for (var i = 0; i < line.length - 1; i++) {
        final ch = line[i];
        if (ch == '\\' && inString) {
          i++;
          continue;
        }
        if (ch == '"') {
          inString = !inString;
        } else if (ch == '/' && line[i + 1] == '/' && !inString) {
          strippedLine = line.substring(0, i).trimRight();
          break;
        }
      }
      result.add(strippedLine);
    }
    return result.join('\n');
  }

  String _extractAgenda(String summaryText) {
    if (summaryText.isEmpty) return '-';
    // JSON 형식이면 내부 summary_text 추출
    var text = summaryText;
    if (text.trimLeft().startsWith('{')) {
      try {
        // 안전한 주석 제거 (문자열 내부 // 보호)
        var cleaned = _safeStripComments(text);
        cleaned = cleaned.replaceAll(RegExp(r',\s*([}\]])'), r'$1');
        final parsed = jsonDecode(cleaned) as Map<String, dynamic>;
        text = parsed['summary_text'] as String? ?? text;
      } catch (_) {}
    }
    // 여전히 JSON이면 '-' 반환
    if (text.trimLeft().startsWith('{')) return '-';
    // 마침표(.)로 끝나는 첫 문장 추출
    final dotIndex = text.indexOf('.');
    if (dotIndex > 0 && dotIndex < 100) {
      return text.substring(0, dotIndex + 1);
    }
    if (text.length > 80) {
      return '${text.substring(0, 80)}...';
    }
    return text;
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

// 마인드맵 탭: 백엔드 AI 생성 API를 통해 관계 추론형 그래프를 표시
class _MindMapTab extends ConsumerWidget {
  final String? taskId;

  const _MindMapTab({required this.taskId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.account_tree_outlined,
        title: '마인드맵 준비 중',
        subtitle: '처리가 완료되지 않았습니다',
      );
    }

    final mindMapAsync = ref.watch(mindMapResultProvider(taskId!));

    return mindMapAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: '마인드맵을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(mindMapResultProvider(taskId!)),
      ),
      data: (MindMapResult result) {
        final root = result.root;
        if (root == null) {
          return const EmptyStateWidget(
            icon: Icons.account_tree_outlined,
            title: '마인드맵을 만들 내용이 없습니다',
            subtitle: 'AI 요약을 먼저 생성해 주세요',
          );
        }

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _MindMapRootNode(
              title: root.title.isNotEmpty ? root.title : '회의 인사이트',
              subtitle: root.summary,
            ),
            const SizedBox(height: 12),
            ...root.children.map((node) => _MindMapGraphNode(node: node)),
            if (result.edges.isNotEmpty) ...[
              const SizedBox(height: 4),
              _MindMapRelations(edges: result.edges),
            ],
          ],
        );
      },
    );
  }

  Widget _buildShimmerLoading() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: List.generate(
          4,
          (_) => const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: ShimmerText(lines: 2),
          ),
        ),
      ),
    );
  }
}

class _MindMapRootNode extends StatelessWidget {
  final String title;
  final String subtitle;

  const _MindMapRootNode({required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer.withAlpha(80),
        border: Border.all(color: theme.colorScheme.primary.withAlpha(80)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.account_tree_outlined, color: theme.colorScheme.primary),
              const SizedBox(width: 8),
              Text(
                title,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          if (subtitle.trim().isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              subtitle,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                height: 1.5,
                color: theme.colorScheme.onSurface,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _MindMapGraphNode extends StatelessWidget {
  final MindMapNode node;
  final int depth;

  const _MindMapGraphNode({required this.node, this.depth = 0});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final leftInset = depth * 14.0;

    return Padding(
      padding: EdgeInsets.only(left: leftInset, bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 9,
                height: 9,
                margin: const EdgeInsets.only(top: 20),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primary,
                  shape: BoxShape.circle,
                ),
              ),
              if (node.children.isNotEmpty)
                Container(
                  width: 1,
                  height: 28,
                  color: theme.dividerColor,
                ),
            ],
          ),
          Container(
            width: 18,
            height: 1,
            margin: const EdgeInsets.only(top: 24),
            color: theme.dividerColor,
          ),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: depth == 0
                    ? theme.colorScheme.surfaceContainerHighest.withAlpha(100)
                    : theme.colorScheme.surface,
                border: Border.all(color: theme.dividerColor),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    node.title.isNotEmpty ? node.title : node.id,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  if (node.summary.trim().isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      node.summary,
                      style: const TextStyle(height: 1.45),
                    ),
                  ],
                  if (node.sourceRefs.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: node.sourceRefs
                          .map((ref) => Chip(
                                label: Text(ref),
                                visualDensity: VisualDensity.compact,
                                materialTapTargetSize:
                                    MaterialTapTargetSize.shrinkWrap,
                              ))
                          .toList(),
                    ),
                  ],
                  if (node.children.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    ...node.children.map(
                      (child) => _MindMapGraphNode(
                        node: child,
                        depth: depth + 1,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MindMapRelations extends StatelessWidget {
  final List<MindMapEdge> edges;

  const _MindMapRelations({required this.edges});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.hub_outlined, size: 20, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  '관계',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ...edges.take(12).map(
                  (edge) => Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      '${edge.source} → ${edge.target} · ${edge.relation}',
                      style: const TextStyle(height: 1.4),
                    ),
                  ),
                ),
          ],
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
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '담당자: ${item.assignee ?? '미지정'}',
                  overflow: TextOverflow.ellipsis,
                  maxLines: 1,
                ),
                if (item.deadline != null)
                  Text(
                    '마감: ${item.deadline}',
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                  ),
              ],
            ),
            isThreeLine: item.deadline != null,
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
