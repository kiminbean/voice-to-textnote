// 결과 화면 - 실제 API 데이터 바인딩 + 에러/빈 상태
// SPEC-APP-003: 액션 아이템 표시, SPEC-APP-004: 주요 결정 사항/다음 단계 표시
// SPEC-EXPORT-001: PDF 내보내기 기능 추가
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
import 'package:voice_to_textnote/services/statistics_api.dart';
import 'package:voice_to_textnote/services/sentiment_api.dart';
import 'package:voice_to_textnote/services/bookmark_api.dart';
import 'package:voice_to_textnote/services/team_api.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';
import 'package:voice_to_textnote/widgets/error_retry_widget.dart';
import 'package:voice_to_textnote/widgets/shimmer_text.dart';
import 'package:voice_to_textnote/widgets/speaker_segment.dart';
import 'package:voice_to_textnote/widgets/find_replace_bar.dart';
import 'package:voice_to_textnote/widgets/audio_player_bar.dart';
import 'package:voice_to_textnote/widgets/tone_timeline.dart';
import 'package:voice_to_textnote/providers/audio_player_provider.dart';
import 'package:voice_to_textnote/providers/qa_provider.dart';
import 'package:voice_to_textnote/services/obsidian_api.dart';
import 'package:url_launcher/url_launcher.dart';

// ConsumerStatefulWidget으로 변경: _isExporting 상태 관리 필요
class ResultScreen extends ConsumerStatefulWidget {
  final String meetingId;

  const ResultScreen({super.key, required this.meetingId});

  @override
  ConsumerState<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends ConsumerState<ResultScreen> {
  bool _isExporting = false;

  Future<void> _export(
    BuildContext context,
    ExportFormat format,
    String? minutesTaskId,
    String? summaryTaskId,
  ) async {
    if (minutesTaskId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('회의록 처리가 완료되지 않아 내보낼 수 없습니다.')),
      );
      return;
    }

    if (_isExporting) return;
    setState(() => _isExporting = true);

    final box = context.findRenderObject() as RenderBox?;
    final shareOrigin = box != null
        ? box.localToGlobal(Offset.zero) & box.size
        : const Rect.fromLTWH(0, 0, 100, 100);

    final (mimeType, subject) = switch (format) {
      ExportFormat.pdf => ('application/pdf', '회의록 PDF'),
      ExportFormat.docx => (
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          '회의록 DOCX',
        ),
      ExportFormat.markdown => ('text/markdown', '회의록 Markdown'),
    };

    try {
      final exportApi = ref.read(exportApiProvider);
      final file = await switch (format) {
        ExportFormat.pdf =>
          exportApi.downloadPdf(minutesTaskId, summaryTaskId: summaryTaskId),
        ExportFormat.docx =>
          exportApi.downloadDocx(minutesTaskId, summaryTaskId: summaryTaskId),
        ExportFormat.markdown => exportApi.downloadMarkdown(minutesTaskId,
            summaryTaskId: summaryTaskId),
      };
      await Share.shareXFiles(
        [XFile(file.path, mimeType: mimeType)],
        subject: subject,
        sharePositionOrigin: shareOrigin,
      );
    } catch (e) {
      if (context.mounted) {
        final label = switch (format) {
          ExportFormat.pdf => 'PDF',
          ExportFormat.docx => 'DOCX',
          ExportFormat.markdown => 'Markdown',
        };
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$label 내보내기 실패: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isExporting = false);
      }
    }
  }

  Future<void> _exportToObsidian(
      BuildContext context, String? minutesTaskId) async {
    if (minutesTaskId == null || minutesTaskId.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('회의록 처리가 완료되지 않아 내보낼 수 없습니다')),
      );
      return;
    }

    setState(() => _isExporting = true);

    try {
      final api = ref.read(obsidianApiProvider);
      final result = await api.exportMeeting(minutesTaskId);

      if (!context.mounted) return;

      if (result.success) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Obsidian에 저장되었습니다'),
            action: result.obsidianUri.isNotEmpty
                ? SnackBarAction(
                    label: '열기',
                    onPressed: () async {
                      await launchUrl(
                        Uri.parse(result.obsidianUri),
                        mode: LaunchMode.externalApplication,
                      );
                    },
                  )
                : null,
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text(
                  'Obsidian 저장 실패: ${result.error ?? "알 수 없는 오류"}')),
        );
      }
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Obsidian 저장 실패: $e')),
      );
    } finally {
      if (mounted) {
        setState(() => _isExporting = false);
      }
    }
  }

  Future<void> _showShareDialog(
      BuildContext context, String? minutesTaskId) async {
    if (minutesTaskId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('회의록 처리가 완료되지 않아 공유할 수 없습니다')),
      );
      return;
    }

    try {
      final teamApi = ref.read(teamApiProvider);
      final teams = await teamApi.getTeams();
      if (!context.mounted) return;

      if (teams.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('가입된 팀이 없습니다. 먼저 팀을 만들어 주세요.')),
        );
        return;
      }

      await showDialog(
        context: context,
        builder: (ctx) => _ShareDialog(
          teams: teams,
          taskId: minutesTaskId,
        ),
      );
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('팀 목록을 불러올 수 없습니다: $e')),
        );
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
      length: 8,
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => Navigator.of(context).canPop()
                ? Navigator.of(context).pop()
                : context.go('/'),
          ),
          title: const Text('회의 결과'),
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
                : PopupMenuButton<String>(
                    icon: const Icon(Icons.ios_share),
                    tooltip: '내보내기',
                    onSelected: (value) {
                      if (value == 'obsidian') {
                        _exportToObsidian(context, minutesTaskId);
                      } else {
                        final format = ExportFormat.values.firstWhere(
                          (e) => e.name == value,
                          orElse: () => ExportFormat.pdf,
                        );
                        _export(context, format, minutesTaskId, summaryTaskId);
                      }
                    },
                    itemBuilder: (_) => [
                      const PopupMenuItem(
                        value: 'pdf',
                        child: Row(children: [
                          Icon(Icons.picture_as_pdf_outlined, size: 20),
                          SizedBox(width: 12),
                          Text('PDF'),
                        ]),
                      ),
                      const PopupMenuItem(
                        value: 'docx',
                        child: Row(children: [
                          Icon(Icons.description_outlined, size: 20),
                          SizedBox(width: 12),
                          Text('DOCX'),
                        ]),
                      ),
                      const PopupMenuItem(
                        value: 'markdown',
                        child: Row(children: [
                          Icon(Icons.code_outlined, size: 20),
                          SizedBox(width: 12),
                          Text('Markdown'),
                        ]),
                      ),
                      const PopupMenuDivider(),
                      const PopupMenuItem(
                        value: 'obsidian',
                        child: Row(children: [
                          Icon(Icons.auto_stories, size: 20),
                          SizedBox(width: 12),
                          Text('Obsidian에 저장'),
                        ]),
                      ),
                    ],
                  ),
            IconButton(
              icon: const Icon(Icons.share_outlined),
              tooltip: '팀에 공유',
              onPressed: () => _showShareDialog(context, minutesTaskId),
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
              Tab(text: 'Q&A'),
              Tab(text: '통계'),
              Tab(text: '감정 분석'),
            ],
          ),
        ),
        body: Column(
          children: [
            Expanded(
              child: TabBarView(
                children: [
                  // 회의 내용 탭: 화자별 원본 발화 세그먼트
                  _TranscriptTab(
                      taskId: minutesTaskId,
                      transcriptionTaskId: meeting?.transcriptionTaskId),
                  // 회의록 탭: 양식 기반 테이블 형태 회의록
                  _MinutesTab(taskId: summaryTaskId, meeting: meeting),
                  // AI 요약 탭: 구조화된 분석 (주요 결정 사항 + 다음 단계)
                  _SummaryTab(taskId: summaryTaskId),
                  // 마인드맵 탭: 백엔드 AI 생성 API 기반 관계 그래프
                  _MindMapTab(taskId: summaryTaskId),
                  // 액션 아이템 탭 (summaryTaskId 사용)
                  _ActionItemsTab(taskId: summaryTaskId),
                  // Q&A 탭: 회의 내용 질문/답변 (SPEC-QA-001)
                  _QATab(taskId: summaryTaskId ?? minutesTaskId),
                  _StatisticsTab(taskId: minutesTaskId),
                  // SPEC-SENTIMENT-001: 감정 분석 전용 탭 (REQ-SEN-007)
                  _SentimentTab(taskId: minutesTaskId),
                ],
              ),
            ),
            // 오디오 플레이어 바 (업로드된 오디오가 있을 때만 표시)
            if (meeting?.transcriptionTaskId != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                child: AudioPlayerBar(taskId: meeting!.transcriptionTaskId!),
              ),
          ],
        ),
      ),
    );
  }
}

// 회의록 탭
class _TranscriptTab extends ConsumerStatefulWidget {
  final String? taskId;
  final String? transcriptionTaskId;

  const _TranscriptTab({required this.taskId, this.transcriptionTaskId});

  @override
  ConsumerState<_TranscriptTab> createState() => _TranscriptTabState();
}

class _TranscriptTabState extends ConsumerState<_TranscriptTab> {
  bool _showSearch = false;
  String _searchQuery = '';
  int _matchCount = 0;
  int _currentMatchIndex = 0;
  final _scrollController = ScrollController();

  void _updateSearch(String query, String content) {
    setState(() {
      _searchQuery = query;
      if (query.isEmpty) {
        _matchCount = 0;
        _currentMatchIndex = 0;
      } else {
        _matchCount = RegExp(RegExp.escape(query), caseSensitive: false)
            .allMatches(content)
            .length;
        if (_matchCount > 0 && _currentMatchIndex >= _matchCount) {
          _currentMatchIndex = _matchCount - 1;
        }
      }
    });
  }

  void _copyToClipboard(String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('클립보드에 복사되었습니다')),
    );
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.article_outlined,
        title: '회의 내용 준비 중',
        subtitle: '처리가 완료되지 않았습니다',
      );
    }

    final segmentsAsync = ref.watch(transcriptSegmentsProvider(widget.taskId!));

    return segmentsAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: '회의록을 불러올 수 없습니다',
        onRetry: () =>
            ref.invalidate(transcriptSegmentsProvider(widget.taskId!)),
      ),
      data: (segments) {
        if (segments.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.article_outlined,
            title: '회의 내용이 없습니다',
            subtitle: '처리가 완료되지 않았을 수 있습니다',
          );
        }

        return _buildSegmentList(segments);
      },
    );
  }

  Widget _buildSegmentList(List<TranscriptSegment> segments) {
    final audioState = ref.watch(audioPlayerProvider);
    final positionSec = audioState.position.inMilliseconds / 1000.0;
    final isPlaying = audioState.playbackState == AudioPlaybackState.playing ||
        audioState.playbackState == AudioPlaybackState.paused;

    final allText = segments.map((s) => s.text).join(' ');

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              IconButton(
                icon: const Icon(Icons.search),
                onPressed: () => setState(() {
                  _showSearch = !_showSearch;
                  if (!_showSearch) {
                    _searchQuery = '';
                    _matchCount = 0;
                  }
                }),
                tooltip: '검색',
              ),
              IconButton(
                icon: const Icon(Icons.copy),
                onPressed: () => _copyToClipboard(allText),
                tooltip: '복사',
              ),
            ],
          ),
        ),
        AnimatedSize(
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeInOut,
          child: _showSearch
              ? FindReplaceBar(
                  searchQuery: _searchQuery,
                  onSearchChanged: (q) => _updateSearch(q, allText),
                  onNext: () {
                    setState(() {
                      _currentMatchIndex =
                          (_currentMatchIndex + 1) % _matchCount;
                    });
                  },
                  onPrevious: () {
                    setState(() {
                      _currentMatchIndex =
                          (_currentMatchIndex - 1 + _matchCount) % _matchCount;
                    });
                  },
                  onClose: () => setState(() {
                    _showSearch = false;
                    _searchQuery = '';
                    _matchCount = 0;
                  }),
                  matchCount: _matchCount,
                  currentMatchIndex: _currentMatchIndex,
                )
              : const SizedBox.shrink(),
        ),
        Expanded(
          child: ListView.builder(
            controller: _scrollController,
            itemCount: segments.length,
            itemBuilder: (_, index) {
              final seg = segments[index];
              final isActive = isPlaying &&
                  positionSec >= seg.start &&
                  positionSec < seg.end;

              return GestureDetector(
                onTap: widget.transcriptionTaskId != null
                    ? () => _seekToSegment(seg.start)
                    : null,
                onLongPress: () => _addBookmark(seg),
                child: SpeakerSegment(
                  speakerName: seg.speakerName,
                  text: seg.text,
                  startTime: Duration(milliseconds: (seg.start * 1000).round()),
                  speakerIndex: seg.speakerIndex,
                  searchQuery: _searchQuery,
                  isHighlighted: isActive,
                  onSpeakerTap: () => _showRenameDialog(segments, index),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  void _seekToSegment(double startSec) {
    ref
        .read(audioPlayerProvider.notifier)
        .seekTo(Duration(milliseconds: (startSec * 1000).round()));
  }

  Future<void> _addBookmark(TranscriptSegment seg) async {
    final noteController = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('북마크 추가'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '[${seg.speakerName}] ${seg.text}',
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: noteController,
              decoration: const InputDecoration(
                labelText: '메모',
                hintText: '이 구간에 대한 메모를 남겨보세요',
                isDense: true,
              ),
              textCapitalization: TextCapitalization.sentences,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('저장'),
          ),
        ],
      ),
    );
    noteController.dispose();

    if (confirmed != true || !mounted) return;

    try {
      final api = ref.read(bookmarkApiProvider);
      await api.create(
        taskId: widget.taskId!,
        segmentStart: seg.start,
        segmentEnd: seg.end,
        textSnippet: seg.text.length > 100
            ? '${seg.text.substring(0, 100)}...'
            : seg.text,
        note: noteController.text.trim().isNotEmpty
            ? noteController.text.trim()
            : null,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('북마크가 추가되었습니다')),
        );
        ref.invalidate(bookmarksProvider(widget.taskId!));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('북마크 추가 실패: $e')),
        );
      }
    }
  }

  void _showRenameDialog(List<TranscriptSegment> segments, int tappedIndex) {
    final tapped = segments[tappedIndex];
    final controller = TextEditingController(text: tapped.speakerName);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('화자 이름 변경'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: '이름',
            hintText: '화자 이름을 입력하세요',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () {
              final newName = controller.text.trim();
              if (newName.isNotEmpty && newName != tapped.speakerName) {
                setState(() {
                  for (int i = 0; i < segments.length; i++) {
                    if (segments[i].speakerName == tapped.speakerName) {
                      segments[i] = TranscriptSegment(
                        speakerName: newName,
                        text: segments[i].text,
                        start: segments[i].start,
                        end: segments[i].end,
                        speakerIndex: segments[i].speakerIndex,
                      );
                    }
                  }
                });
              }
              Navigator.pop(ctx);
            },
            child: const Text('변경'),
          ),
        ],
      ),
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
              ShimmerText(lines: 8),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatisticsTab extends ConsumerStatefulWidget {
  final String? taskId;

  const _StatisticsTab({required this.taskId});

  @override
  ConsumerState<_StatisticsTab> createState() => _StatisticsTabState();
}

class _StatisticsTabState extends ConsumerState<_StatisticsTab> {
  @override
  Widget build(BuildContext context) {
    if (widget.taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.bar_chart_outlined,
        title: '통계 준비 중',
        subtitle: '회의록 처리가 완료되지 않았습니다',
      );
    }

    final statsAsync = ref.watch(statisticsProvider(widget.taskId!));

    return statsAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => ErrorRetryWidget(
        message: '통계를 불러올 수 없습니다',
        onRetry: () => ref.invalidate(statisticsProvider(widget.taskId!)),
      ),
      data: (stats) => buildContent(context, stats),
    );
  }

  Widget buildContent(BuildContext context, StatisticsResponse stats) {
    final theme = Theme.of(context);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('회의 개요', style: theme.textTheme.titleMedium),
                const SizedBox(height: 12),
                _statRow(context, '총 세그먼트', '${stats.totalSegments}개'),
                _statRow(context, '총 단어 수', '${stats.totalWords}개'),
                _statRow(context, '총 발화 시간',
                    _formatDuration(stats.totalDurationSeconds)),
                _statRow(context, '참여 화자', '${stats.uniqueSpeakers}명'),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('화자별 발화 시간', style: theme.textTheme.titleMedium),
                const SizedBox(height: 12),
                ...stats.speakers.map((s) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(s.speaker,
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w600)),
                              Text(
                                '${_formatDuration(s.speakingTimeSeconds)} (${(s.speakingRatio * 100).toStringAsFixed(1)}%)',
                                style: theme.textTheme.bodySmall,
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(4),
                            child: LinearProgressIndicator(
                              value: s.speakingRatio,
                              minHeight: 8,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '${s.segmentCount}회 발화, ${s.wordCount}단어',
                            style: theme.textTheme.labelSmall,
                          ),
                        ],
                      ),
                    )),
              ],
            ),
          ),
        ),
        if (stats.topKeywords.isNotEmpty) ...[
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('주요 키워드', style: theme.textTheme.titleMedium),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: stats.topKeywords
                        .map((k) => Chip(
                              label: Text('${k.keyword} (${k.count})'),
                              materialTapTargetSize:
                                  MaterialTapTargetSize.shrinkWrap,
                            ))
                        .toList(),
                  ),
                ],
              ),
            ),
          ),
        ],
        // SPEC-SENTIMENT-001: 감정 분석은 전용 _SentimentTab으로 이관됨
        // 기존 silent fallback (SizedBox.shrink on error) 제거됨 (REQ-SEN-010)
      ],
    );
  }

  Widget _statRow(BuildContext context, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodyMedium),
          Text(value,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  String _formatDuration(double seconds) {
    final m = (seconds / 60).floor();
    final s = (seconds % 60).round();
    return m > 0 ? '$m분 $s초' : '$s초';
  }
}

// SPEC-SENTIMENT-001: 감정 분석 전용 탭 (REQ-SEN-007/008/009/010)
// 전체 감정 분포, 화자별 precomputed 데이터, emotional_timeline, 오류 재시도 UI 제공
class _SentimentTab extends ConsumerWidget {
  final String? taskId;

  const _SentimentTab({required this.taskId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (taskId == null || taskId!.isEmpty) {
      return const Center(child: Text('감정 분석을 불러올 수 없습니다.'));
    }

    final sentimentAsync = ref.watch(sentimentFullProvider(taskId!));

    return sentimentAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      // REQ-SEN-010: 오류를 숨기지 않고 ErrorRetryWidget으로 표시
      error: (error, _) => ErrorRetryWidget(
        message: '감정 분석을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(sentimentFullProvider(taskId!)),
      ),
      // SPEC-TONE-001: meetingId 전달 → ToneSection 독립 watch (오류 격리, REQ-TONE-013)
      data: (response) =>
          _SentimentContent(response: response, meetingId: taskId!),
    );
  }
}

class _SentimentContent extends StatelessWidget {
  final SentimentFullResponse response;
  // SPEC-TONE-001: ToneSection에 전달할 meetingId (minutesTaskId와 동일)
  final String meetingId;

  const _SentimentContent({required this.response, required this.meetingId});

  Color _sentimentColor(String sentiment) {
    switch (sentiment) {
      case 'positive':
        return Colors.green;
      case 'negative':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  IconData _emotionIcon(String emotion) {
    switch (emotion) {
      case 'joy':
      case 'satisfaction':
        return Icons.sentiment_very_satisfied;
      case 'anger':
        return Icons.sentiment_very_dissatisfied;
      case 'sadness':
        return Icons.sentiment_dissatisfied;
      case 'surprise':
        return Icons.sentiment_neutral;
      case 'frustration':
      case 'fear':
        return Icons.warning_amber;
      default:
        return Icons.sentiment_neutral;
    }
  }

  String _formatTime(double seconds) {
    final m = (seconds / 60).floor();
    final s = (seconds % 60).round();
    return m > 0 ? '$m:${s.toString().padLeft(2, '0')}' : '$s초';
  }

  String _sentimentLabel(String sentiment) {
    switch (sentiment) {
      case 'positive':
        return '긍정';
      case 'negative':
        return '부정';
      default:
        return '중립';
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // 빈 응답 처리 (segments도 speakers도 timeline도 없는 경우)
    if (response.segments.isEmpty &&
        response.speakers.isEmpty &&
        response.emotionalTimeline.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.sentiment_neutral, size: 64, color: Colors.grey[400]),
              const SizedBox(height: 16),
              Text('감정 분석 데이터가 없습니다', style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              Text(
                '회의록이 완료된 후 감정 분석을 실행해 주세요.',
                style: theme.textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // 1. 전체 감정 요약 카드 (REQ-SEN-008: overall_sentiment/emotion)
        _buildOverallCard(theme),
        const SizedBox(height: 16),

        // 2. 전체 감정 분포 (REQ-SEN-008)
        if (response.speakers.isNotEmpty) _buildDistributionCard(theme),
        const SizedBox(height: 16),

        // 3. 화자별 감정 (REQ-SEN-008: SpeakerSentiment precomputed 데이터)
        if (response.speakers.isNotEmpty) ...[
          _buildSpeakerSection(theme),
          const SizedBox(height: 16),
        ],

        // 4. 감정 변화 타임라인 (REQ-SEN-009: emotional_timeline)
        if (response.emotionalTimeline.isNotEmpty) _buildTimelineSection(theme),

        // 5. 톤 타임라인 (SPEC-TONE-001 REQ-TONE-012)
        // @MX:NOTE: ToneSection은 별도 ConsumerWidget으로 toneProvider를 독립 watch
        // → tone 실패 시 sentiment 카드에 영향 없음 (오류 격리, REQ-TONE-013)
        const SizedBox(height: 16),
        ToneSection(meetingId: meetingId),
      ],
    );
  }

  Widget _buildOverallCard(ThemeData theme) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(_emotionIcon(response.overallEmotion), size: 48),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('전체 분위기', style: theme.textTheme.bodySmall),
                  const SizedBox(height: 4),
                  Text(
                    '${_sentimentLabel(response.overallSentiment)} · ${response.overallEmotion}',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // REQ-SEN-008: 화자별 감정 비율 합산으로 전체 분포 계산
  Widget _buildDistributionCard(ThemeData theme) {
    double totalPositive = 0;
    double totalNeutral = 0;
    double totalNegative = 0;

    for (final speaker in response.speakers) {
      totalPositive += speaker.positiveRatio;
      totalNeutral += speaker.neutralRatio;
      totalNegative += speaker.negativeRatio;
    }

    final count = response.speakers.length;
    if (count > 0) {
      totalPositive /= count;
      totalNeutral /= count;
      totalNegative /= count;
    }

    final total = totalPositive + totalNeutral + totalNegative;
    if (total == 0) return const SizedBox.shrink();

    final positiveRatio = totalPositive / total;
    final neutralRatio = totalNeutral / total;
    final negativeRatio = totalNegative / total;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('감정 분포', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: SizedBox(
                height: 28,
                child: Row(
                  children: [
                    if (positiveRatio > 0)
                      Expanded(
                        flex: (positiveRatio * 100).round().clamp(1, 100),
                        child: Container(
                          color: Colors.green,
                          alignment: Alignment.center,
                          child: Text(
                            '${(positiveRatio * 100).toStringAsFixed(0)}%',
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold),
                          ),
                        ),
                      ),
                    if (neutralRatio > 0)
                      Expanded(
                        flex: (neutralRatio * 100).round().clamp(1, 100),
                        child: Container(
                          color: Colors.grey,
                          alignment: Alignment.center,
                          child: Text(
                            '${(neutralRatio * 100).toStringAsFixed(0)}%',
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold),
                          ),
                        ),
                      ),
                    if (negativeRatio > 0)
                      Expanded(
                        flex: (negativeRatio * 100).round().clamp(1, 100),
                        child: Container(
                          color: Colors.red,
                          alignment: Alignment.center,
                          child: Text(
                            '${(negativeRatio * 100).toStringAsFixed(0)}%',
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                _legendDot(Colors.green, '긍정'),
                const SizedBox(width: 12),
                _legendDot(Colors.grey, '중립'),
                const SizedBox(width: 12),
                _legendDot(Colors.red, '부정'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // REQ-SEN-008: 백엔드 SpeakerSentiment precomputed 데이터 사용 (클라이언트 재계산 금지)
  Widget _buildSpeakerSection(ThemeData theme) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('화자별 감정', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            ...response.speakers
                .map((speaker) => _buildSpeakerRow(theme, speaker)),
          ],
        ),
      ),
    );
  }

  Widget _buildSpeakerRow(ThemeData theme, SpeakerSentiment speaker) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(_emotionIcon(speaker.dominantEmotion), size: 18),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  speaker.speaker,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              Text(
                '주요 감정: ${speaker.dominantEmotion}',
                style: theme.textTheme.bodySmall,
              ),
            ],
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              if (speaker.positiveRatio > 0)
                Expanded(
                  flex: (speaker.positiveRatio * 100).round().clamp(1, 100),
                  child: Container(height: 8, color: Colors.green),
                ),
              if (speaker.neutralRatio > 0)
                Expanded(
                  flex: (speaker.neutralRatio * 100).round().clamp(1, 100),
                  child: Container(height: 8, color: Colors.grey),
                ),
              if (speaker.negativeRatio > 0)
                Expanded(
                  flex: (speaker.negativeRatio * 100).round().clamp(1, 100),
                  child: Container(height: 8, color: Colors.red),
                ),
            ],
          ),
        ],
      ),
    );
  }

  // REQ-SEN-009: emotional_timeline 시간 순서 시각화
  Widget _buildTimelineSection(ThemeData theme) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('감정 변화 타임라인', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            ...response.emotionalTimeline
                .map((entry) => _buildTimelineEntry(theme, entry)),
          ],
        ),
      ),
    );
  }

  Widget _buildTimelineEntry(ThemeData theme, EmotionTimelineEntry entry) {
    final color = _sentimentColor(entry.sentiment);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(
            width: 56,
            child: Text(
              _formatTime(entry.time),
              style: theme.textTheme.bodySmall?.copyWith(
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
          Container(width: 4, height: 24, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.speaker,
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 13),
                ),
                Text(
                  '${_sentimentLabel(entry.sentiment)} · ${entry.emotion}',
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
          ),
          Icon(_emotionIcon(entry.emotion), size: 18, color: color),
        ],
      ),
    );
  }

  Widget _legendDot(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11)),
      ],
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

  void _copyToClipboard(SummaryResult result) {
    final buffer = StringBuffer();
    final now = meeting?.createdAt ?? DateTime.now();
    final dateStr =
        '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';

    buffer.writeln('회의록_$dateStr');
    buffer.writeln('---');

    if (result.sections.isNotEmpty) {
      for (final entry in result.sections.entries) {
        buffer.writeln('[${entry.key}]');
        final value = _editedSections[entry.key] ?? entry.value;
        buffer.writeln(value.isNotEmpty ? value : '-');
        buffer.writeln();
      }
    } else {
      buffer.writeln('[회의 안건]');
      buffer.writeln(_extractAgenda(result.summaryText));
      buffer.writeln();

      buffer.writeln('[회의 내용]');
      buffer.writeln(result.summaryText);
      buffer.writeln();

      if (result.keyDecisions.isNotEmpty) {
        buffer.writeln('[결정 사항]');
        for (var i = 0; i < result.keyDecisions.length; i++) {
          buffer.writeln('${i + 1}. ${result.keyDecisions[i]}');
        }
        buffer.writeln();
      }

      if (result.nextSteps.isNotEmpty) {
        buffer.writeln('[향후 계획]');
        for (var i = 0; i < result.nextSteps.length; i++) {
          buffer.writeln('${i + 1}. ${result.nextSteps[i]}');
        }
        buffer.writeln();
      }
    }

    Clipboard.setData(ClipboardData(text: buffer.toString()));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('클립보드에 복사되었습니다')),
    );
  }

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
                  IconButton(
                    icon: const Icon(Icons.copy),
                    onPressed: () => _copyToClipboard(result),
                    tooltip: '복사',
                  ),
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
                  style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.primary),
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
    final tableLayout =
        (result.templateStructure?['table_layout'] as List<dynamic>?) ?? [];

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
                  ? _buildRowsFromLayout(
                      tableLayout, result, headerBg, contentBg, borderColor)
                  // table_layout 없으면 sections 기반 단순 렌더링
                  : result.sections.entries.map((entry) {
                      final isLarge =
                          entry.key.contains('내용') || entry.value.length > 100;
                      final value = entry.value.isNotEmpty ? entry.value : '-';
                      final row = _tableRow2Col(
                        entry.key,
                        headerBg,
                        value,
                        isLarge ? contentBg : null,
                        borderColor,
                        minHeight: isLarge ? 150 : 0,
                      );
                      return _isEditing
                          ? GestureDetector(
                              onTap: () => _editCell(
                                  entry.key, value == '-' ? '' : value),
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
                  child: Text(label1,
                      style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                          color: theme.colorScheme.onSurface),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis),
                ),
              ),
              Container(width: 1, color: borderColor),
              Expanded(
                child: GestureDetector(
                  onTap: () => _editCell(label1, value1),
                  child: Container(
                    decoration: BoxDecoration(
                        border: Border.all(color: editBorder, width: 1)),
                    padding: const EdgeInsets.all(10),
                    child: Text(value1,
                        style: TextStyle(
                            fontSize: 13, color: theme.colorScheme.onSurface),
                        softWrap: true),
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
                  child: Text(label2,
                      style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                          color: theme.colorScheme.onSurface),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis),
                ),
              ),
              Container(width: 1, color: borderColor),
              Expanded(
                child: GestureDetector(
                  onTap: () => _editCell(label2, value2),
                  child: Container(
                    decoration: BoxDecoration(
                        border: Border.all(color: editBorder, width: 1)),
                    padding: const EdgeInsets.all(10),
                    child: Text(value2,
                        style: TextStyle(
                            fontSize: 13, color: theme.colorScheme.onSurface),
                        softWrap: true),
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
            label1,
            headerBg,
            value1,
            null,
            label2,
            headerBg,
            value2,
            null,
            borderColor,
          );
        } else {
          final labels = cells.map((c) => c['label'] as String? ?? '').toList();
          splitRow = _tableRowNCol(
            labels,
            labels.map((l) => _resolveValue(l, result)).toList(),
            headerBg,
            borderColor,
          );
        }
        // 편집 모드 - split 행의 첫 번째 라벨로 편집 다이얼로그
        if (_isEditing) {
          // 편집 모드: 각 셀을 개별적으로 편집 가능하도록 IntrinsicHeight Row 내부에 GestureDetector 삽입
          rows.add(_wrapSplitRowWithEdit(
              cells, result, headerBg, contentBg, borderColor));
        } else {
          rows.add(splitRow);
        }
      } else {
        final label = rowDef['label'] as String? ?? '';
        final value = _resolveValue(label, result);
        final isLarge = label.contains('내용') ||
            label.contains('논의') ||
            label.contains('이슈') ||
            value.length > 100;
        final row = _tableRow2Col(
          label,
          headerBg,
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
                  '프로젝트명',
                  headerBg,
                  meeting?.title ?? '-',
                  null,
                  '회의일시',
                  headerBg,
                  '$dateStr $timeStr',
                  null,
                  borderColor,
                ),
                // 3행: 팀명 | 작성자 (4열 구조)
                _wrapEditSplitRow(
                  '팀명',
                  headerBg,
                  '-',
                  null,
                  '작성자',
                  headerBg,
                  '-',
                  null,
                  borderColor,
                ),
                // 4행: 참석자
                _wrapEditRow('참석자', '-', headerBg, null, borderColor),
                // 5행: 회의안건 (summaryText 첫 문장 추출)
                _wrapEditRow('회의안건', _extractAgenda(result.summaryText),
                    headerBg, null, borderColor),
                // 6행: 회의내용 (큰 영역, 노란 배경)
                _wrapEditRow('회의내용', result.summaryText, headerBg, contentBg,
                    borderColor,
                    minHeight: 200),
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
  Widget _wrapEditRow(String label, String value, Color labelBg,
      Color? contentBg, Color borderColor,
      {double minHeight = 0}) {
    final displayValue =
        _editedSections.containsKey(label) ? _editedSections[label]! : value;
    final row = _tableRow2Col(label, labelBg,
        displayValue.isEmpty ? '-' : displayValue, contentBg, borderColor,
        minHeight: minHeight);
    if (!_isEditing) return row;
    final theme = Theme.of(context);
    return GestureDetector(
      onTap: () => _editCell(label, displayValue == '-' ? '' : displayValue),
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(
              color: theme.colorScheme.primary.withAlpha(80), width: 1),
        ),
        child: row,
      ),
    );
  }

  // 편집 모드 래핑: 4열 split 행 — 각 셀 개별 편집
  Widget _wrapEditSplitRow(
    String label1,
    Color labelBg1,
    String content1,
    Color? contentBg1,
    String label2,
    Color labelBg2,
    String content2,
    Color? contentBg2,
    Color borderColor,
  ) {
    final displayVal1 = _editedSections.containsKey(label1)
        ? _editedSections[label1]!
        : content1;
    final displayVal2 = _editedSections.containsKey(label2)
        ? _editedSections[label2]!
        : content2;

    if (!_isEditing) {
      return _tableRow4Col(label1, labelBg1, displayVal1, contentBg1, label2,
          labelBg2, displayVal2, contentBg2, borderColor);
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
                child: Text(label1,
                    style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                        color: theme.colorScheme.onSurface),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis),
              ),
            ),
            Container(width: 1, color: borderColor),
            Expanded(
              child: GestureDetector(
                onTap: () =>
                    _editCell(label1, displayVal1 == '-' ? '' : displayVal1),
                child: Container(
                  decoration: BoxDecoration(
                      border: Border.all(color: editBorder, width: 1)),
                  padding: const EdgeInsets.all(10),
                  child: Text(displayVal1,
                      style: TextStyle(
                          fontSize: 13, color: theme.colorScheme.onSurface),
                      softWrap: true),
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
                child: Text(label2,
                    style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                        color: theme.colorScheme.onSurface),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis),
              ),
            ),
            Container(width: 1, color: borderColor),
            Expanded(
              child: GestureDetector(
                onTap: () =>
                    _editCell(label2, displayVal2 == '-' ? '' : displayVal2),
                child: Container(
                  decoration: BoxDecoration(
                      border: Border.all(color: editBorder, width: 1)),
                  padding: const EdgeInsets.all(10),
                  child: Text(displayVal2,
                      style: TextStyle(
                          fontSize: 13, color: theme.colorScheme.onSurface),
                      softWrap: true),
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
    String label,
    Color labelBg,
    String content,
    Color? contentBg,
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
                  style: TextStyle(
                      height: 1.7,
                      fontSize: 13,
                      color: theme.colorScheme.onSurface),
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
    String label1,
    Color labelBg1,
    String content1,
    Color? contentBg1,
    String label2,
    Color labelBg2,
    String content2,
    Color? contentBg2,
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
                  style: TextStyle(
                      fontSize: 13, color: theme.colorScheme.onSurface),
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
                  style: TextStyle(
                      fontSize: 13, color: theme.colorScheme.onSurface),
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
                    style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 11,
                        color: theme.colorScheme.onSurface),
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
                    style: TextStyle(
                        fontSize: 11, color: theme.colorScheme.onSurface),
                    softWrap: true,
                  ),
                ),
              ),
              if (i < labels.length - 1)
                Container(width: 1, color: borderColor),
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
class _SummaryTab extends ConsumerStatefulWidget {
  final String? taskId;

  const _SummaryTab({required this.taskId});

  @override
  ConsumerState<_SummaryTab> createState() => _SummaryTabState();
}

class _SummaryTabState extends ConsumerState<_SummaryTab> {
  bool _showSearch = false;
  String _searchQuery = '';
  int _matchCount = 0;
  int _currentMatchIndex = 0;

  void _updateSearch(String query, SummaryResult result) {
    setState(() {
      _searchQuery = query;
      if (query.isEmpty) {
        _matchCount = 0;
        _currentMatchIndex = 0;
      } else {
        final regex = RegExp(RegExp.escape(query), caseSensitive: false);
        int count = regex.allMatches(result.summaryText).length;
        for (final decision in result.keyDecisions) {
          count += regex.allMatches(decision).length;
        }
        for (final step in result.nextSteps) {
          count += regex.allMatches(step).length;
        }
        _matchCount = count;
        if (_matchCount > 0 && _currentMatchIndex >= _matchCount) {
          _currentMatchIndex = _matchCount - 1;
        }
      }
    });
  }

  void _copyToClipboard(SummaryResult result) {
    final buffer = StringBuffer();
    buffer.writeln('AI 요약');
    buffer.writeln('---');
    buffer.writeln(result.summaryText);

    if (result.keyDecisions.isNotEmpty) {
      buffer.writeln('\n주요 결정 사항');
      buffer.writeln('---');
      for (var i = 0; i < result.keyDecisions.length; i++) {
        buffer.writeln('${i + 1}. ${result.keyDecisions[i]}');
      }
    }

    if (result.nextSteps.isNotEmpty) {
      buffer.writeln('\n다음 단계');
      buffer.writeln('---');
      for (var i = 0; i < result.nextSteps.length; i++) {
        buffer.writeln('${i + 1}. ${result.nextSteps[i]}');
      }
    }

    Clipboard.setData(ClipboardData(text: buffer.toString()));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('클립보드에 복사되었습니다')),
    );
  }

  Widget _buildHighlightedText(String text, TextStyle? style) {
    if (_searchQuery.isEmpty) {
      return Text(text, style: style);
    }

    final matches = RegExp(RegExp.escape(_searchQuery), caseSensitive: false)
        .allMatches(text)
        .toList();
    if (matches.isEmpty) {
      return Text(text, style: style);
    }

    final spans = <TextSpan>[];
    int lastMatchEnd = 0;

    for (final match in matches) {
      if (match.start > lastMatchEnd) {
        spans.add(TextSpan(text: text.substring(lastMatchEnd, match.start)));
      }
      spans.add(TextSpan(
        text: text.substring(match.start, match.end),
        style: const TextStyle(
            backgroundColor: Colors.yellow, color: Colors.black),
      ));
      lastMatchEnd = match.end;
    }

    if (lastMatchEnd < text.length) {
      spans.add(TextSpan(text: text.substring(lastMatchEnd)));
    }

    return RichText(
      text: TextSpan(
        style: style ?? DefaultTextStyle.of(context).style,
        children: spans,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // task ID가 없으면 빈 상태 표시
    if (widget.taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.summarize_outlined,
        title: 'AI 요약 준비 중',
        subtitle: '처리가 완료되지 않았습니다',
      );
    }

    final summaryAsync = ref.watch(summaryResultProvider(widget.taskId!));

    return summaryAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: 'AI 요약을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(summaryResultProvider(widget.taskId!)),
      ),
      data: (SummaryResult result) {
        if (result.summaryText.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.summarize_outlined,
            title: 'AI 요약이 없습니다',
          );
        }

        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  IconButton(
                    icon: const Icon(Icons.search),
                    onPressed: () => setState(() {
                      _showSearch = !_showSearch;
                      if (!_showSearch) {
                        _searchQuery = '';
                        _matchCount = 0;
                      }
                    }),
                    tooltip: '검색',
                  ),
                  IconButton(
                    icon: const Icon(Icons.copy),
                    onPressed: () => _copyToClipboard(result),
                    tooltip: '복사',
                  ),
                ],
              ),
            ),
            AnimatedSize(
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeInOut,
              child: _showSearch
                  ? FindReplaceBar(
                      searchQuery: _searchQuery,
                      onSearchChanged: (q) => _updateSearch(q, result),
                      onNext: () {
                        setState(() {
                          _currentMatchIndex =
                              (_currentMatchIndex + 1) % _matchCount;
                        });
                      },
                      onPrevious: () {
                        setState(() {
                          _currentMatchIndex =
                              (_currentMatchIndex - 1 + _matchCount) %
                                  _matchCount;
                        });
                      },
                      onClose: () => setState(() {
                        _showSearch = false;
                        _searchQuery = '';
                        _matchCount = 0;
                      }),
                      matchCount: _matchCount,
                      currentMatchIndex: _currentMatchIndex,
                    )
                  : const SizedBox.shrink(),
            ),
            Expanded(
              child: SingleChildScrollView(
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
                        _buildHighlightedText(
                          result.summaryText,
                          const TextStyle(height: 1.6),
                        ),
                        // 주요 결정 사항 섹션 (SPEC-APP-004 REQ-APP-042)
                        if (result.keyDecisions.isNotEmpty) ...[
                          const SizedBox(height: 16),
                          Text(
                            '주요 결정 사항',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const Divider(),
                          ...result.keyDecisions.asMap().entries.map(
                                (e) => Padding(
                                  padding: const EdgeInsets.only(bottom: 4),
                                  child: _buildHighlightedText(
                                    '${e.key + 1}. ${e.value}',
                                    const TextStyle(height: 1.6),
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
                          ...result.nextSteps.asMap().entries.map(
                                (e) => Padding(
                                  padding: const EdgeInsets.only(bottom: 4),
                                  child: _buildHighlightedText(
                                    '${e.key + 1}. ${e.value}',
                                    const TextStyle(height: 1.6),
                                  ),
                                ),
                              ),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
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
              Icon(Icons.account_tree_outlined,
                  color: theme.colorScheme.primary),
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
                Icon(Icons.hub_outlined,
                    size: 20, color: theme.colorScheme.primary),
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
        final priorityColor = _priorityColors[item.priority] ?? Colors.orange;

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

// Q&A 탭: 회의 내용에 대한 자연어 질문/답변 (SPEC-QA-001)
class _QATab extends ConsumerStatefulWidget {
  final String? taskId;

  const _QATab({required this.taskId});

  @override
  ConsumerState<_QATab> createState() => _QATabState();
}

class _QATabState extends ConsumerState<_QATab> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.chat_outlined,
        title: 'Q&A 준비 중',
        subtitle: '회의 처리가 완료되면 질문할 수 있습니다',
      );
    }

    final qaState = ref.watch(qaProvider(widget.taskId!));
    final theme = Theme.of(context);

    return Column(
      children: [
        Expanded(
          child: qaState.messages.isEmpty
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.chat_bubble_outline,
                          size: 48, color: theme.colorScheme.outline),
                      const SizedBox(height: 12),
                      const Text('회의 내용에 대해 질문해 보세요'),
                      const SizedBox(height: 4),
                      Text(
                        '예: "어떤 결정이 내려졌나요?"',
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: qaState.messages.length,
                  itemBuilder: (ctx, i) {
                    final msg = qaState.messages[i];
                    return _ChatBubble(
                      message: msg,
                      theme: theme,
                    );
                  },
                ),
        ),
        if (qaState.isLoading)
          const Padding(
            padding: EdgeInsets.all(8),
            child: LinearProgressIndicator(),
          ),
        // 입력 바
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  decoration: InputDecoration(
                    hintText: '질문을 입력하세요...',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 10,
                    ),
                  ),
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(qaState),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                icon: const Icon(Icons.send),
                onPressed: qaState.isLoading ? null : () => _send(qaState),
              ),
            ],
          ),
        ),
      ],
    );
  }

  void _send(QAState qaState) {
    final text = _controller.text.trim();
    if (text.isEmpty || qaState.isLoading) return;
    _controller.clear();
    ref.read(qaProvider(widget.taskId!).notifier).ask(text);
    _scrollToBottom();
  }
}

class _ChatBubble extends StatelessWidget {
  final ChatMessage message;
  final ThemeData theme;

  const _ChatBubble({required this.message, required this.theme});

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final align = isUser ? Alignment.centerRight : Alignment.centerLeft;
    final bg = isUser
        ? theme.colorScheme.primary
        : theme.colorScheme.surfaceContainerHighest;
    final fg =
        isUser ? theme.colorScheme.onPrimary : theme.colorScheme.onSurface;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      alignment: align,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * 0.8,
        ),
        child: Column(
          crossAxisAlignment:
              isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: bg,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(isUser ? 16 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 16),
                ),
              ),
              child: Text(
                message.text,
                style: TextStyle(color: fg, height: 1.5),
              ),
            ),
            if (message.sources.isNotEmpty) ...[
              const SizedBox(height: 4),
              ...message.sources.map((s) => Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      '[${s.speaker ?? "화자"}] ${s.text}',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.outline,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }
}

// 팀 공유 다이얼로그
class _ShareDialog extends ConsumerStatefulWidget {
  final List<Team> teams;
  final String taskId;

  const _ShareDialog({required this.teams, required this.taskId});

  @override
  ConsumerState<_ShareDialog> createState() => _ShareDialogState();
}

class _ShareDialogState extends ConsumerState<_ShareDialog> {
  bool _isSharing = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return AlertDialog(
      title: const Text('팀에 공유'),
      content: SizedBox(
        width: double.maxFinite,
        child: ListView.builder(
          shrinkWrap: true,
          itemCount: widget.teams.length,
          itemBuilder: (_, i) {
            final team = widget.teams[i];
            return ListTile(
              leading: CircleAvatar(
                backgroundColor: theme.colorScheme.primaryContainer,
                child: Text(
                    team.name.isNotEmpty ? team.name[0].toUpperCase() : '?'),
              ),
              title: Text(team.name),
              subtitle: team.description != null && team.description!.isNotEmpty
                  ? Text(team.description!,
                      maxLines: 1, overflow: TextOverflow.ellipsis)
                  : null,
              trailing: _isSharing
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.send),
              onTap: _isSharing ? null : () => _shareToTeam(team),
            );
          },
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('닫기'),
        ),
      ],
    );
  }

  Future<void> _shareToTeam(Team team) async {
    setState(() => _isSharing = true);
    try {
      final api = ref.read(teamApiProvider);
      await api.shareMeeting(widget.taskId, team.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("'${team.name}' 팀에 공유했습니다")),
        );
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('공유 실패: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isSharing = false);
    }
  }
}
