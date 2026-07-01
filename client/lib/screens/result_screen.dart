// 결과 화면 - 실제 API 데이터 바인딩 + 에러/빈 상태
// SPEC-APP-003: 액션 아이템 표시, SPEC-APP-004: 주요 결정 사항/다음 단계 표시
// SPEC-EXPORT-001: PDF 내보내기 기능 추가
import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:dio/dio.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:share_plus/share_plus.dart';
import 'package:voice_to_textnote/models/action_item.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/models/mind_map_result.dart';
import 'package:voice_to_textnote/models/promise_radar.dart';
import 'package:voice_to_textnote/models/sales_contact_brief.dart';
import 'package:voice_to_textnote/models/summary_result.dart';
import 'package:voice_to_textnote/models/speaker_profile.dart';
import 'package:voice_to_textnote/models/study_pack.dart';
import 'package:voice_to_textnote/models/translation.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/providers/obsidian_provider.dart';
import 'package:voice_to_textnote/providers/sales_contact_brief_provider.dart';
import 'package:voice_to_textnote/providers/speaker_provider.dart';
import 'package:voice_to_textnote/providers/team_provider.dart';
import 'package:voice_to_textnote/providers/result_provider.dart';
import 'package:voice_to_textnote/providers/study_pack_provider.dart';
import 'package:voice_to_textnote/providers/translation_provider.dart';
import 'package:voice_to_textnote/services/export_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';
import 'package:voice_to_textnote/services/speaker_api.dart';
import 'package:voice_to_textnote/services/statistics_api.dart';
import 'package:voice_to_textnote/services/sentiment_api.dart';
import 'package:voice_to_textnote/services/bookmark_api.dart';
import 'package:voice_to_textnote/services/auth_service.dart';
import 'package:voice_to_textnote/services/promise_radar_api.dart';
import 'package:voice_to_textnote/services/team_api.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';
import 'package:voice_to_textnote/widgets/error_retry_widget.dart';
import 'package:voice_to_textnote/widgets/shimmer_text.dart';
import 'package:voice_to_textnote/widgets/speaker_segment.dart';
import 'package:voice_to_textnote/widgets/find_replace_bar.dart';
import 'package:voice_to_textnote/widgets/audio_player_bar.dart';
import 'package:voice_to_textnote/widgets/audio_enhancement_panel.dart';
import 'package:voice_to_textnote/widgets/tone_timeline.dart';
import 'package:voice_to_textnote/providers/audio_player_provider.dart';
import 'package:voice_to_textnote/providers/qa_provider.dart';
import 'package:url_launcher/url_launcher.dart';

const _googleTasksScope = 'https://www.googleapis.com/auth/tasks';

// ConsumerStatefulWidget으로 변경: _isExporting 상태 관리 필요
class ResultScreen extends ConsumerStatefulWidget {
  final String meetingId;

  const ResultScreen({super.key, required this.meetingId});

  @override
  ConsumerState<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends ConsumerState<ResultScreen> {
  bool _isExporting = false;
  String? _prefetchedMinutesTaskId;
  String? _prefetchedSummaryTaskId;

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

    if (_isExporting) return;

    setState(() => _isExporting = true);

    try {
      final notifier = ref.read(obsidianExportProvider.notifier);
      await notifier.exportMeeting(minutesTaskId);
      final exportState = ref.read(obsidianExportProvider);
      if (exportState.hasError) {
        throw exportState.error!;
      }
      final result = exportState.value;
      if (result == null) {
        throw StateError('Obsidian 저장 결과를 받지 못했습니다.');
      }

      if (!context.mounted) return;

      if (result.success) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result.filePath.isNotEmpty
                ? '현재 서버/Mac의 Obsidian vault에 저장되었습니다: ${result.filePath}'
                : '현재 서버/Mac의 Obsidian vault에 저장되었습니다'),
            action: result.obsidianUri.isNotEmpty
                ? SnackBarAction(
                    label: '열기',
                    onPressed: () async {
                      try {
                        final launched = await launchUrl(
                          Uri.parse(result.obsidianUri),
                          mode: LaunchMode.externalApplication,
                        );
                        if (!launched && context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content: Text(
                                    'Obsidian을 열 수 없습니다. 앱이 설치되어 있는지 확인하세요.')),
                          );
                        }
                      } catch (e) {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Obsidian 열기 실패: $e')),
                          );
                        }
                      }
                    },
                  )
                : null,
          ),
        );
      } else {
        _showObsidianFailureSnackBar(
          context,
          result.error ?? '알 수 없는 오류',
        );
      }
    } catch (e) {
      if (!context.mounted) return;
      _showObsidianFailureSnackBar(context, '$e');
    } finally {
      if (mounted) {
        setState(() => _isExporting = false);
      }
    }
  }

  void _showObsidianFailureSnackBar(BuildContext context, String message) {
    final needsConfig = message.contains('OBSIDIAN_NOT_CONFIGURED') ||
        message.contains('vault 경로가 설정되지 않았습니다') ||
        message.contains('OBSIDIAN_VAULT_INVALID');
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(needsConfig
            ? 'Obsidian 저장 실패: 현재 서버/Mac의 vault 경로를 설정해주세요.'
            : 'Obsidian 저장 실패: $message'),
        action: needsConfig
            ? SnackBarAction(
                label: '설정',
                onPressed: () => context.push('/settings'),
              )
            : null,
      ),
    );
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
    final promiseRadarTaskId =
        summaryTaskId ?? (meeting == null ? widget.meetingId : null);
    _scheduleAuxiliaryPrefetch(
      minutesTaskId: minutesTaskId,
      summaryTaskId: summaryTaskId,
    );
    final sharedTeamsAsync = meeting?.sharedTeamIds.isNotEmpty == true
        ? ref.watch(teamListProvider)
        : const AsyncData(<Team>[]);

    return DefaultTabController(
      length: 12,
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_rounded),
            onPressed: () => Navigator.of(context).canPop()
                ? Navigator.of(context).pop()
                : context.go('/'),
          ),
          title: const Text('AI Notes'),
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
                    icon: const Icon(Icons.ios_share_rounded),
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
            IconButton(
              icon: const Icon(Icons.more_horiz_rounded),
              tooltip: '설정',
              onPressed: () => context.push('/settings'),
            ),
          ],
          bottom: const TabBar(
            isScrollable: true,
            tabs: [
              Tab(text: 'AI 요약'),
              Tab(text: '회의 내용'),
              Tab(text: '액션 아이템'),
              Tab(text: '약속 레이더'),
              Tab(text: '회의록'),
              Tab(text: '마인드맵'),
              Tab(text: '영업'),
              Tab(text: '학습'),
              Tab(text: '번역'),
              Tab(text: 'Q&A'),
              Tab(text: '통계'),
              Tab(text: '감정 분석'),
            ],
          ),
        ),
        body: Column(
          children: [
            _ResultHero(
              meeting: meeting,
              sharedTeamsAsync: sharedTeamsAsync,
              onExportTap: () => _showExportSheet(
                context,
                minutesTaskId,
                summaryTaskId,
              ),
              onShareTap: () => _showShareDialog(context, minutesTaskId),
            ),
            Expanded(
              child: TabBarView(
                children: [
                  // AI 요약 탭: 구조화된 분석 (주요 결정 사항 + 다음 단계)
                  _SummaryTab(
                    taskId: summaryTaskId,
                    minutesTaskId: minutesTaskId,
                  ),
                  // 회의 내용 탭: 화자별 원본 발화 세그먼트
                  _TranscriptTab(
                      taskId: minutesTaskId,
                      transcriptionTaskId: meeting?.transcriptionTaskId),
                  // 액션 아이템 탭 (summaryTaskId 사용)
                  _ActionItemsTab(taskId: summaryTaskId),
                  // 약속 레이더: 과거 회의와 현재 회의의 약속/결정 연속성 분석
                  _PromiseRadarTab(taskId: promiseRadarTaskId),
                  // 회의록 탭: 양식 기반 테이블 형태 회의록
                  _MinutesTab(taskId: summaryTaskId, meeting: meeting),
                  // 마인드맵 탭: 백엔드 AI 생성 API 기반 관계 그래프
                  _MindMapTab(taskId: summaryTaskId),
                  // 영업 탭: 고객/딜 후속 브리프
                  _SalesContactBriefTab(taskId: minutesTaskId),
                  // 학습 탭: 회의록 기반 Study Pack 생성
                  _StudyTab(taskId: minutesTaskId),
                  // 번역 탭: 회의록/요약 기반 다국어 번역
                  _TranslationTab(
                    minutesTaskId: minutesTaskId,
                    summaryTaskId: summaryTaskId,
                  ),
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
            if (meeting?.audioFilePath != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                child: AudioEnhancementLauncher(
                  audioFilePath: meeting!.audioFilePath!,
                ),
              ),
          ],
        ),
      ),
    );
  }

  void _scheduleAuxiliaryPrefetch({
    required String? minutesTaskId,
    required String? summaryTaskId,
  }) {
    if (_prefetchedMinutesTaskId == minutesTaskId &&
        _prefetchedSummaryTaskId == summaryTaskId) {
      return;
    }
    _prefetchedMinutesTaskId = minutesTaskId;
    _prefetchedSummaryTaskId = summaryTaskId;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _prefetchAuxiliaryResults(
        minutesTaskId: minutesTaskId,
        summaryTaskId: summaryTaskId,
      );
    });
  }

  void _prefetchAuxiliaryResults({
    required String? minutesTaskId,
    required String? summaryTaskId,
  }) {
    if (summaryTaskId != null && summaryTaskId.isNotEmpty) {
      _ignorePrefetch(ref.read(summaryResultProvider(summaryTaskId).future));
      _ignorePrefetch(ref.read(mindMapResultProvider(summaryTaskId).future));
      _ignorePrefetch(
        ref.read(
          translationProvider(
            TranslationRequest(
              taskId: summaryTaskId,
              targetLanguage: 'en',
              sourceType: 'summary',
            ),
          ).future,
        ),
      );
    }

    if (minutesTaskId != null && minutesTaskId.isNotEmpty) {
      _ignorePrefetch(ref.read(statisticsProvider(minutesTaskId).future));
      _ignorePrefetch(
        ref.read(
          translationProvider(
            TranslationRequest(
              taskId: minutesTaskId,
              targetLanguage: 'en',
              sourceType: 'minutes',
            ),
          ).future,
        ),
      );
      _ignorePrefetch(
        ref.read(
          salesContactBriefProvider(
            SalesContactBriefRequest(taskId: minutesTaskId),
          ).future,
        ),
      );
      _ignorePrefetch(
        ref.read(
          studyPackProvider(
            StudyPackRequest(taskId: minutesTaskId),
          ).future,
        ),
      );
      _ignorePrefetch(ref.read(sentimentFullProvider(minutesTaskId).future));
      _ignorePrefetch(ref.read(toneProvider(minutesTaskId).future));
    }
  }

  void _ignorePrefetch<T>(Future<T> future) {
    unawaited(future.then<void>((_) {}, onError: (_, __) {}));
  }

  Future<void> _showExportSheet(
    BuildContext context,
    String? minutesTaskId,
    String? summaryTaskId,
  ) async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.lg,
            AppSpacing.sm,
            AppSpacing.lg,
            AppSpacing.xl,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Share & Export',
                style: Theme.of(ctx).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: AppSpacing.md),
              _ExportSheetTile(
                icon: Icons.picture_as_pdf_outlined,
                label: 'Export PDF',
                onTap: () {
                  Navigator.of(ctx).pop();
                  _export(
                      context, ExportFormat.pdf, minutesTaskId, summaryTaskId);
                },
              ),
              _ExportSheetTile(
                icon: Icons.description_outlined,
                label: 'Export DOCX',
                onTap: () {
                  Navigator.of(ctx).pop();
                  _export(
                      context, ExportFormat.docx, minutesTaskId, summaryTaskId);
                },
              ),
              _ExportSheetTile(
                icon: Icons.code_outlined,
                label: 'Export Markdown',
                onTap: () {
                  Navigator.of(ctx).pop();
                  _export(context, ExportFormat.markdown, minutesTaskId,
                      summaryTaskId);
                },
              ),
              _ExportSheetTile(
                icon: Icons.auto_stories,
                label: 'Save to Obsidian',
                onTap: () {
                  Navigator.of(ctx).pop();
                  _exportToObsidian(context, minutesTaskId);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ResultHero extends StatelessWidget {
  final Meeting? meeting;
  final AsyncValue<List<Team>> sharedTeamsAsync;
  final VoidCallback onExportTap;
  final VoidCallback onShareTap;

  const _ResultHero({
    required this.meeting,
    required this.sharedTeamsAsync,
    required this.onExportTap,
    required this.onShareTap,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    final duration = meeting?.duration;
    final durationLabel = duration == null
        ? 'Processing'
        : '${duration.inMinutes}m ${duration.inSeconds.remainder(60)}s';

    return Container(
      margin: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.md,
        AppSpacing.lg,
        AppSpacing.sm,
      ),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: AppRadius.brLg,
        border: Border.all(color: scheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: scheme.primarySoft,
                  borderRadius: AppRadius.brMd,
                ),
                child: Icon(Icons.auto_awesome_rounded, color: scheme.primary),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      meeting?.title ?? '회의 요약 생성 중',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Summary, transcript, action items',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: scheme.textSecondary,
                          ),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    _ShareVisibilityLine(
                      meeting: meeting,
                      teamsAsync: sharedTeamsAsync,
                    ),
                  ],
                ),
              ),
              _MetricPill(label: durationLabel),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: onExportTap,
                  icon: const Icon(Icons.ios_share_rounded),
                  label: const Text('Share & Export'),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              IconButton.filledTonal(
                onPressed: onShareTap,
                icon: const Icon(Icons.groups_2_outlined),
                tooltip: '팀에 공유',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ShareVisibilityLine extends StatelessWidget {
  final Meeting? meeting;
  final AsyncValue<List<Team>> teamsAsync;

  const _ShareVisibilityLine({
    required this.meeting,
    required this.teamsAsync,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    final sharedTeamIds = meeting?.sharedTeamIds ?? const <String>[];
    final isShared = sharedTeamIds.isNotEmpty;
    return Row(
      children: [
        Icon(
          isShared ? Icons.groups_2_outlined : Icons.lock_outline_rounded,
          size: 14,
          color: isShared ? scheme.primary : scheme.textSecondary,
        ),
        const SizedBox(width: AppSpacing.xs),
        Expanded(
          child: Text(
            _shareVisibilityLabel(sharedTeamIds, teamsAsync),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: isShared ? scheme.primary : scheme.textSecondary,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ),
      ],
    );
  }

  String _shareVisibilityLabel(
    List<String> sharedTeamIds,
    AsyncValue<List<Team>> teamsAsync,
  ) {
    if (sharedTeamIds.isEmpty) {
      return '비공개 · 나만 볼 수 있음';
    }

    return teamsAsync.when(
      data: (teams) {
        final teamNamesById = {for (final team in teams) team.id: team.name};
        final names = sharedTeamIds
            .map((teamId) => teamNamesById[teamId])
            .whereType<String>()
            .where((name) => name.isNotEmpty)
            .toList(growable: false);
        if (names.isEmpty) {
          return '팀 공유 · ${sharedTeamIds.length}개 팀';
        }
        if (names.length == 1) {
          return '${names.first} 팀에 공유 중';
        }
        if (names.length == 2) {
          return '${names.join(', ')} 팀에 공유 중';
        }
        return '${names.take(2).join(', ')} 외 ${names.length - 2}개 팀에 공유 중';
      },
      loading: () => '팀 공유 · 공유 팀 불러오는 중',
      error: (_, __) => '팀 공유 · ${sharedTeamIds.length}개 팀',
    );
  }
}

class _MetricPill extends StatelessWidget {
  final String label;
  const _MetricPill({required this.label});

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: scheme.surfaceAlt,
        borderRadius: AppRadius.brPill,
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: scheme.textSecondary,
              fontWeight: FontWeight.w800,
            ),
      ),
    );
  }
}

class _ExportSheetTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _ExportSheetTile({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon),
      title: Text(label),
      trailing: const Icon(Icons.chevron_right_rounded),
      onTap: onTap,
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
  final Set<String> _promptedDefaultSpeakerIds = <String>{};
  bool _renameDialogOpen = false;
  bool _voiceprintBackfillAttempted = false;

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

        _scheduleVoiceprintBackfill();
        _scheduleDefaultSpeakerNamePrompt(segments);
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
                  endTime: Duration(milliseconds: (seg.end * 1000).round()),
                  speakerIndex: seg.speakerIndex,
                  isEstimatedSpeaker: seg.isEstimatedSpeaker,
                  voiceprintSimilarity: seg.voiceprintSimilarity,
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

  void _scheduleVoiceprintBackfill() {
    if (_voiceprintBackfillAttempted) return;
    _voiceprintBackfillAttempted = true;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      try {
        final result = await ref.read(speakerApiProvider).backfillVoiceprints();
        if (!mounted || result.enrolledProfiles <= 0) return;
        ref.invalidate(speakerListProvider(widget.taskId));
        ref.invalidate(speakerNameMapProvider(widget.taskId));
        if (widget.taskId != null) {
          ref.invalidate(transcriptSegmentsProvider(widget.taskId!));
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('기존 화자 ${result.enrolledProfiles}명의 목소리 정보를 보강했습니다'),
          ),
        );
      } catch (_) {
        // Backfill is opportunistic; normal transcript viewing must not fail.
      }
    });
  }

  void _scheduleDefaultSpeakerNamePrompt(List<TranscriptSegment> segments) {
    if (_renameDialogOpen) return;

    final index = segments.indexWhere((segment) {
      if (!_isDefaultSpeakerName(segment.speakerName)) return false;
      final promptKey = segment.speakerId ?? segment.speakerName;
      return !_promptedDefaultSpeakerIds.contains(promptKey);
    });
    if (index < 0) return;

    final promptKey = segments[index].speakerId ?? segments[index].speakerName;
    _promptedDefaultSpeakerIds.add(promptKey);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || _renameDialogOpen) return;
      _showRenameDialog(segments, index);
    });
  }

  void _showRenameDialog(List<TranscriptSegment> segments, int tappedIndex) {
    _renameDialogOpen = true;
    final tapped = segments[tappedIndex];
    final controller = TextEditingController(text: tapped.speakerName);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(_isDefaultSpeakerName(tapped.speakerName)
            ? '이 화자의 이름을 알려주세요'
            : '화자 이름 변경'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_isDefaultSpeakerName(tapped.speakerName)) ...[
              const Text('다음 녹음에서 같은 화자 라벨에 이 이름을 자동으로 적용합니다.'),
              const SizedBox(height: 12),
            ],
            TextField(
              controller: controller,
              autofocus: true,
              textInputAction: TextInputAction.done,
              decoration: const InputDecoration(
                labelText: '화자 이름',
                hintText: '예: 영자, 철수',
              ),
              onSubmitted: (_) => _saveSpeakerName(
                ctx,
                segments,
                tapped,
                controller.text.trim(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => _saveSpeakerName(
              ctx,
              segments,
              tapped,
              controller.text.trim(),
            ),
            child: const Text('저장'),
          ),
        ],
      ),
    ).whenComplete(() {
      _renameDialogOpen = false;
    });
  }

  bool _isDefaultSpeakerName(String name) =>
      RegExp(r'^Speaker \d+$').hasMatch(name);

  Future<void> _saveSpeakerName(
    BuildContext dialogContext,
    List<TranscriptSegment> segments,
    TranscriptSegment tapped,
    String newName,
  ) async {
    if (newName.isEmpty) {
      Navigator.pop(dialogContext);
      return;
    }

    Navigator.pop(dialogContext);

    final speakerId = tapped.speakerId;
    if (speakerId == null || widget.taskId == null) return;

    try {
      final authState = ref.read(authStateProvider);
      final accessToken = await ref.read(authServiceProvider).getAccessToken();
      if (!authState.isAuthenticated ||
          accessToken == null ||
          accessToken.isEmpty) {
        throw StateError('화자 이름 저장은 로그인 후 사용할 수 있습니다.');
      }

      final saved = await _upsertGlobalSpeakerName(speakerId, newName);
      if (newName != tapped.speakerName && mounted) {
        setState(() {
          for (int i = 0; i < segments.length; i++) {
            final sameSpeaker = tapped.speakerId != null
                ? segments[i].speakerId == tapped.speakerId
                : segments[i].speakerName == tapped.speakerName;
            if (sameSpeaker) {
              segments[i] = TranscriptSegment(
                speakerId: segments[i].speakerId,
                speakerName: newName,
                text: segments[i].text,
                start: segments[i].start,
                end: segments[i].end,
                speakerIndex: segments[i].speakerIndex,
                isEstimatedSpeaker: false,
                voiceprintSimilarity: segments[i].voiceprintSimilarity,
              );
            }
          }
        });
      }
      ref.invalidate(speakerListProvider(widget.taskId));
      ref.invalidate(speakerNameMapProvider(widget.taskId));
      ref.invalidate(transcriptSegmentsProvider(widget.taskId!));
      ref.invalidate(statisticsProvider(widget.taskId!));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_speakerSaveMessage(saved))),
        );
      }
    } catch (e) {
      final message = _speakerSaveErrorMessage(e);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message)),
        );
      }
    }
  }

  String _speakerSaveErrorMessage(Object error) {
    if (error is DioException && error.response?.statusCode == 401) {
      Future.microtask(() => ref.read(authStateProvider.notifier).checkAuth());
      return '화자 이름 저장은 로그인 후 사용할 수 있습니다. 다시 로그인해 주세요.';
    }
    if (error is StateError) {
      return error.message;
    }
    return '화자 이름 저장 실패: $error';
  }

  String _speakerSaveMessage(SpeakerProfile profile) {
    switch (profile.voiceprintEnrollmentStatus) {
      case 'enrolled':
      case 'already_enrolled':
        return '화자 이름과 목소리 정보를 저장했습니다';
      case 'unavailable':
        return '화자 이름은 저장했지만 목소리 샘플은 부족합니다';
      default:
        return '화자 이름을 저장했습니다';
    }
  }

  Future<SpeakerProfile> _upsertGlobalSpeakerName(
      String speakerId, String displayName) async {
    final api = ref.read(speakerApiProvider);
    final profiles = await api.list();
    SpeakerProfile? existing;
    for (final profile in profiles) {
      if (profile.taskId == null && profile.speakerLabel == speakerId) {
        existing = profile;
        break;
      }
    }

    if (existing == null) {
      return api.create(SpeakerProfileCreate(
        speakerLabel: speakerId,
        displayName: displayName,
        enrollmentTaskId: widget.taskId,
      ));
    } else {
      return api.update(
        existing.id,
        SpeakerProfileUpdate(
          displayName: displayName,
          enrollmentTaskId: widget.taskId,
          enrollmentSpeakerLabel: speakerId,
        ),
      );
    }
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
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        // 회의 개요 — 그리드 카드
        _OverviewCard(stats: stats, formatDuration: _formatDuration),
        const SizedBox(height: AppSpacing.lg),
        // 화자별 발화 시간
        Card(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  const Icon(Icons.bar_chart_rounded, size: 18),
                  const SizedBox(width: AppSpacing.sm),
                  Text('화자별 발화 시간', style: theme.textTheme.titleMedium),
                ]),
                const SizedBox(height: AppSpacing.md),
                ...stats.speakers.map((s) => Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.md),
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
                                style: theme.textTheme.bodySmall?.copyWith(
                                  fontFeatures: const [
                                    FontFeature.tabularFigures()
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(4),
                            child: LinearProgressIndicator(
                              value: s.speakingRatio,
                              minHeight: 6,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${s.segmentCount}회 발화 · ${s.wordCount}단어',
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
          const SizedBox(height: AppSpacing.lg),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    const Icon(Icons.tag_rounded, size: 18),
                    const SizedBox(width: AppSpacing.sm),
                    Text('주요 키워드', style: theme.textTheme.titleMedium),
                  ]),
                  const SizedBox(height: AppSpacing.md),
                  Wrap(
                    spacing: AppSpacing.sm,
                    runSpacing: AppSpacing.sm,
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
      ],
    );
  }

  String _formatDuration(double seconds) {
    final m = (seconds / 60).floor();
    final s = (seconds % 60).round();
    return m > 0 ? '$m분 $s초' : '$s초';
  }
}

/// 회의 개요 통계 카드 — 2x2 그리드 레이아웃
class _OverviewCard extends StatelessWidget {
  final StatisticsResponse stats;
  final String Function(double) formatDuration;
  const _OverviewCard({required this.stats, required this.formatDuration});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final items = [
      _StatItem(
          Icons.record_voice_over_outlined, '세그먼트', '${stats.totalSegments}'),
      _StatItem(Icons.text_snippet_outlined, '총 단어', '${stats.totalWords}'),
      _StatItem(Icons.timer_outlined, '발화 시간',
          formatDuration(stats.totalDurationSeconds)),
      _StatItem(Icons.groups_outlined, '참여 화자', '${stats.uniqueSpeakers}명'),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Icon(Icons.insights_rounded, size: 18),
              const SizedBox(width: AppSpacing.sm),
              Text('회의 개요', style: theme.textTheme.titleMedium),
            ]),
            const SizedBox(height: AppSpacing.md),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 2,
              mainAxisSpacing: AppSpacing.md,
              crossAxisSpacing: AppSpacing.md,
              childAspectRatio: 2.8,
              children: items.map((item) => _StatTile(item: item)).toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatItem {
  final IconData icon;
  final String label;
  final String value;
  const _StatItem(this.icon, this.label, this.value);
}

class _StatTile extends StatelessWidget {
  final _StatItem item;
  const _StatTile({required this.item});

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md, vertical: AppSpacing.sm),
      decoration: BoxDecoration(
        color: scheme.surfaceAlt,
        borderRadius: AppRadius.brMd,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Row(children: [
            Icon(item.icon, size: 14, color: scheme.textTertiary),
            const SizedBox(width: 4),
            Text(item.label,
                style: theme(context).textTheme.labelSmall?.copyWith(
                      color: scheme.textTertiary,
                    )),
          ]),
          const SizedBox(height: 2),
          Text(
            item.value,
            style: theme(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }

  ThemeData theme(BuildContext context) => Theme.of(context);
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
        return AppColors.success;
      case 'negative':
        return AppColors.error;
      default:
        return const Color(0xFF9CA3AF);
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

    if (response.segments.isEmpty &&
        response.speakers.isEmpty &&
        response.emotionalTimeline.isEmpty) {
      return const EmptyStateWidget(
        icon: Icons.sentiment_neutral_rounded,
        title: '감정 분석 데이터가 없습니다',
        subtitle: '회의록이 완료된 후 감정 분석을 실행해 주세요.',
      );
    }

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        // 1. 전체 감정 요약 카드 (REQ-SEN-008: overall_sentiment/emotion)
        _buildOverallCard(theme),
        const SizedBox(height: AppSpacing.lg),

        // 2. 전체 감정 분포 (REQ-SEN-008)
        if (response.speakers.isNotEmpty) _buildDistributionCard(theme),
        const SizedBox(height: AppSpacing.lg),

        // 3. 화자별 감정 (REQ-SEN-008: SpeakerSentiment precomputed 데이터)
        if (response.speakers.isNotEmpty) ...[
          _buildSpeakerSection(theme),
          const SizedBox(height: AppSpacing.lg),
        ],

        // 4. 감정 변화 타임라인 (REQ-SEN-009: emotional_timeline)
        if (response.emotionalTimeline.isNotEmpty) _buildTimelineSection(theme),

        // 5. 톤 타임라인 (SPEC-TONE-001 REQ-TONE-012)
        const SizedBox(height: AppSpacing.lg),
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
                          color: AppColors.success,
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
                          color: const Color(0xFF9CA3AF),
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
                          color: AppColors.error,
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
                _legendDot(AppColors.success, '긍정'),
                const SizedBox(width: 12),
                _legendDot(const Color(0xFF9CA3AF), '중립'),
                const SizedBox(width: 12),
                _legendDot(AppColors.error, '부정'),
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
                  child: const ColoredBox(
                      color: AppColors.success,
                      child: SizedBox(height: 8, width: double.infinity)),
                ),
              if (speaker.neutralRatio > 0)
                Expanded(
                  flex: (speaker.neutralRatio * 100).round().clamp(1, 100),
                  child: const ColoredBox(
                      color: Color(0xFF9CA3AF),
                      child: SizedBox(height: 8, width: double.infinity)),
                ),
              if (speaker.negativeRatio > 0)
                Expanded(
                  flex: (speaker.negativeRatio * 100).round().clamp(1, 100),
                  child: const ColoredBox(
                      color: AppColors.error,
                      child: SizedBox(height: 8, width: double.infinity)),
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
  final String? minutesTaskId;

  const _SummaryTab({
    required this.taskId,
    required this.minutesTaskId,
  });

  @override
  ConsumerState<_SummaryTab> createState() => _SummaryTabState();
}

class _SmartSummaryModeOption {
  final String value;
  final String label;

  const _SmartSummaryModeOption(this.value, this.label);
}

const _smartSummaryModeOptions = [
  _SmartSummaryModeOption('executive', '경영진'),
  _SmartSummaryModeOption('detailed', '상세'),
  _SmartSummaryModeOption('bullet_points', '불릿'),
  _SmartSummaryModeOption('action_oriented', '액션 중심'),
  _SmartSummaryModeOption('sentiment_focused', '감정'),
  _SmartSummaryModeOption('lecture_notes', '강의 노트'),
  _SmartSummaryModeOption('sales_follow_up', '영업 후속'),
  _SmartSummaryModeOption('sermon_notes', '설교 노트'),
  _SmartSummaryModeOption('research_interview', '리서치'),
  _SmartSummaryModeOption('decision_log', '결정 로그'),
  _SmartSummaryModeOption('action_only', '액션만'),
  _SmartSummaryModeOption('soap_note', 'SOAP 노트'),
];

class _SummaryTabState extends ConsumerState<_SummaryTab> {
  bool _showSearch = false;
  String _searchQuery = '';
  int _matchCount = 0;
  int _currentMatchIndex = 0;
  String _selectedSummaryMode = 'executive';
  AsyncValue<Map<String, dynamic>>? _modeSummary;
  AsyncValue<Map<String, dynamic>>? _modeSummaryHistory;

  @override
  void initState() {
    super.initState();
    _loadModeSummaryHistory();
  }

  @override
  void didUpdateWidget(covariant _SummaryTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.minutesTaskId != widget.minutesTaskId) {
      _modeSummary = null;
      _loadModeSummaryHistory();
    }
  }

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

  Future<void> _generateModeSummary() async {
    final minutesTaskId = widget.minutesTaskId;
    if (minutesTaskId == null || minutesTaskId.isEmpty) {
      return;
    }

    setState(() {
      _modeSummary = const AsyncValue.loading();
    });

    final api = ref.read(summaryApiProvider);
    final result = await AsyncValue.guard(
      () => api.createSmartSummary(
        minutesTaskId,
        summaryMode: _selectedSummaryMode,
      ),
    );

    if (!mounted) return;
    setState(() {
      _modeSummary = result;
      if (result.hasValue) {
        _modeSummaryHistory = AsyncValue.data(_mergeModeSummaryHistory(
          _modeSummaryHistory?.valueOrNull,
          result.value!,
        ));
      }
    });
  }

  String _modeSummaryText(Map<String, dynamic> data) {
    final result = data['result'];
    if (result is Map<String, dynamic>) {
      final content = result['summary_content'];
      if (content is Map<String, dynamic>) {
        final summaryText = content['summary_text'];
        if (summaryText is String && summaryText.trim().isNotEmpty) {
          return summaryText;
        }
      }
    }
    return '요약 결과가 비어 있습니다.';
  }

  Future<void> _loadModeSummaryHistory() async {
    final minutesTaskId = widget.minutesTaskId;
    if (minutesTaskId == null || minutesTaskId.isEmpty) {
      return;
    }

    setState(() {
      _modeSummaryHistory = const AsyncValue.loading();
    });

    final api = ref.read(summaryApiProvider);
    final result = await AsyncValue.guard(
      () => api.getSmartSummaryHistory(minutesTaskId),
    );

    if (!mounted) return;
    setState(() {
      _modeSummaryHistory = result;
      final firstStoredMode = _firstStoredMode(result.valueOrNull);
      if (firstStoredMode != null &&
          _modeHistoryVersionsForMode(result.valueOrNull, _selectedSummaryMode)
              .isEmpty) {
        _selectedSummaryMode = firstStoredMode;
      }
    });
  }

  Map<String, dynamic> _mergeModeSummaryHistory(
    Map<String, dynamic>? current,
    Map<String, dynamic> generated,
  ) {
    final merged = Map<String, dynamic>.from(
      current ??
          {
            'minutes_task_id': widget.minutesTaskId,
            'histories': <String, dynamic>{},
          },
    );
    final rawHistories = merged['histories'];
    final histories = rawHistories is Map
        ? Map<String, dynamic>.from(rawHistories)
        : <String, dynamic>{};
    final versions = histories[_selectedSummaryMode] is List
        ? List<dynamic>.from(histories[_selectedSummaryMode] as List)
        : <dynamic>[];
    versions.insert(0, {
      'task_id': generated['task_id'],
      'summary_mode': _selectedSummaryMode,
      'summary_text': _modeSummaryText(generated),
      'created_at': generated['created_at'],
      'completed_at': generated['completed_at'],
      'result': generated['result'],
    });
    histories[_selectedSummaryMode] = versions;
    merged['histories'] = histories;
    return merged;
  }

  List<Map<String, dynamic>> _modeHistoryVersions(Map<String, dynamic> data) {
    return _modeHistoryVersionsForMode(data, _selectedSummaryMode);
  }

  List<Map<String, dynamic>> _modeHistoryVersionsForMode(
    Map<String, dynamic>? data,
    String mode,
  ) {
    if (data == null) {
      return const [];
    }
    final rawHistories = data['histories'];
    if (rawHistories is! Map) {
      return const [];
    }
    final rawVersions = rawHistories[mode];
    if (rawVersions is! List) {
      return const [];
    }
    return rawVersions
        .whereType<Map>()
        .map((entry) => Map<String, dynamic>.from(entry))
        .where((entry) {
      final text = entry['summary_text'];
      return text is String && text.trim().isNotEmpty;
    }).toList();
  }

  String? _firstStoredMode(Map<String, dynamic>? data) {
    if (data == null) {
      return null;
    }
    final rawHistories = data['histories'];
    if (rawHistories is! Map) {
      return null;
    }
    for (final entry in rawHistories.entries) {
      if (_modeHistoryVersionsForMode(data, entry.key.toString()).isNotEmpty) {
        return entry.key.toString();
      }
    }
    return null;
  }

  Widget _buildStoredModeSummary(Map<String, dynamic> data) {
    final versions = _modeHistoryVersions(data).isNotEmpty
        ? _modeHistoryVersions(data)
        : _allModeHistoryVersions(data);
    if (versions.isEmpty) {
      return const SizedBox.shrink();
    }

    final latest = versions.first;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Theme.of(context).dividerColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '저장된 모드 요약',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              Text(
                '저장된 버전 ${versions.length}개',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            latest['summary_text'] as String,
            style: const TextStyle(height: 1.5),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _allModeHistoryVersions(
      Map<String, dynamic> data) {
    final rawHistories = data['histories'];
    if (rawHistories is! Map) {
      return const [];
    }
    final versions = <Map<String, dynamic>>[];
    for (final entry in rawHistories.entries) {
      versions.addAll(_modeHistoryVersionsForMode(data, entry.key.toString()));
    }
    return versions;
  }

  Widget _buildModeSummaryPanel() {
    final modeSummary = _modeSummary;
    final canGenerate =
        widget.minutesTaskId != null && widget.minutesTaskId!.isNotEmpty;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '목적별 요약',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final mode in _smartSummaryModeOptions)
                  ChoiceChip(
                    label: Text(mode.label),
                    selected: _selectedSummaryMode == mode.value,
                    onSelected: (_) {
                      setState(() {
                        _selectedSummaryMode = mode.value;
                        _modeSummary = null;
                      });
                    },
                  ),
              ],
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: canGenerate ? _generateModeSummary : null,
              icon: const Icon(Icons.auto_awesome),
              label: const Text('모드 요약 생성'),
            ),
            if (!canGenerate) ...[
              const SizedBox(height: 8),
              Text(
                '회의록 처리가 완료되면 목적별 요약을 생성할 수 있습니다.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (modeSummary != null) ...[
              const SizedBox(height: 16),
              modeSummary.when(
                loading: () => const ShimmerText(lines: 3),
                error: (error, _) => Text(
                  '목적별 요약을 생성할 수 없습니다.',
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
                data: (data) => Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Theme.of(context).dividerColor),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '모드 요약 결과',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _modeSummaryText(data),
                        style: const TextStyle(height: 1.5),
                      ),
                    ],
                  ),
                ),
              ),
            ],
            if (_modeSummaryHistory != null &&
                _modeSummary?.valueOrNull == null) ...[
              const SizedBox(height: 16),
              _modeSummaryHistory!.when(
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
                data: _buildStoredModeSummary,
              ),
            ],
          ],
        ),
      ),
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

    final scheme = AppColors.of(context);
    final highlightBg =
        scheme.isDark ? const Color(0xCCF59E0B) : const Color(0xCCFDE047);

    for (final match in matches) {
      if (match.start > lastMatchEnd) {
        spans.add(TextSpan(text: text.substring(lastMatchEnd, match.start)));
      }
      spans.add(TextSpan(
        text: text.substring(match.start, match.end),
        style:
            TextStyle(backgroundColor: highlightBg, color: scheme.textPrimary),
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
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildModeSummaryPanel(),
                    const SizedBox(height: 16),
                    Card(
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
                  ],
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

class _TranslationLanguageOption {
  final String value;
  final String label;

  const _TranslationLanguageOption(this.value, this.label);
}

const _translationLanguageOptions = [
  _TranslationLanguageOption('en', 'English'),
  _TranslationLanguageOption('ko', '한국어'),
  _TranslationLanguageOption('ja', '日本語'),
  _TranslationLanguageOption('zh', '中文'),
];

class _TranslationTab extends ConsumerStatefulWidget {
  final String? minutesTaskId;
  final String? summaryTaskId;

  const _TranslationTab({
    required this.minutesTaskId,
    required this.summaryTaskId,
  });

  @override
  ConsumerState<_TranslationTab> createState() => _TranslationTabState();
}

class _TranslationTabState extends ConsumerState<_TranslationTab> {
  String _targetLanguage = 'en';
  String _sourceType = 'summary';

  @override
  Widget build(BuildContext context) {
    final taskId = _sourceType == 'summary'
        ? widget.summaryTaskId ?? widget.minutesTaskId
        : widget.minutesTaskId ?? widget.summaryTaskId;

    if (taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.translate_outlined,
        title: '번역할 결과가 없습니다',
        subtitle: '회의록 또는 요약이 완료되면 번역을 생성할 수 있습니다',
      );
    }

    final request = TranslationRequest(
      taskId: taskId,
      targetLanguage: _targetLanguage,
      sourceType: _sourceType,
    );
    final translationAsync = ref.watch(translationProvider(request));

    return translationAsync.when(
      loading: () => const Padding(
        padding: EdgeInsets.all(16),
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(16),
            child: ShimmerText(lines: 6),
          ),
        ),
      ),
      error: (error, _) => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _TranslationControls(
              sourceType: _sourceType,
              targetLanguage: _targetLanguage,
              hasSummary: widget.summaryTaskId != null,
              hasMinutes: widget.minutesTaskId != null,
              onSourceChanged: _setSourceType,
              onLanguageChanged: _setTargetLanguage,
            ),
            const SizedBox(height: 16),
            ErrorRetryWidget(
              message: '번역을 불러올 수 없습니다',
              onRetry: () => ref.invalidate(translationProvider(request)),
            ),
          ],
        ),
      ),
      data: (translation) => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _TranslationControls(
              sourceType: _sourceType,
              targetLanguage: _targetLanguage,
              hasSummary: widget.summaryTaskId != null,
              hasMinutes: widget.minutesTaskId != null,
              onSourceChanged: _setSourceType,
              onLanguageChanged: _setTargetLanguage,
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: () => _copyTranslation(context, translation),
                    icon: const Icon(Icons.copy_all_outlined),
                    label: const Text('번역 복사'),
                  ),
                  FilledButton.tonalIcon(
                    onPressed: () => ref
                        .read(translationProvider(request).notifier)
                        .regenerate(),
                    icon: const Icon(Icons.refresh_rounded),
                    label: const Text('다시 번역'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            _TranslationResultCard(translation: translation),
            if (translation.sourceExcerpt.trim().isNotEmpty) ...[
              const SizedBox(height: 12),
              _TranslationSourceCard(translation: translation),
            ],
          ],
        ),
      ),
    );
  }

  void _setSourceType(String sourceType) {
    if (sourceType == _sourceType) return;
    setState(() => _sourceType = sourceType);
  }

  void _setTargetLanguage(String targetLanguage) {
    if (targetLanguage == _targetLanguage) return;
    setState(() => _targetLanguage = targetLanguage);
  }

  Future<void> _copyTranslation(
    BuildContext context,
    TranslationResult translation,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    await Clipboard.setData(
      ClipboardData(text: translation.translatedText),
    );
    messenger.showSnackBar(
      const SnackBar(content: Text('번역을 복사했습니다')),
    );
  }
}

class _TranslationControls extends StatelessWidget {
  final String sourceType;
  final String targetLanguage;
  final bool hasSummary;
  final bool hasMinutes;
  final ValueChanged<String> onSourceChanged;
  final ValueChanged<String> onLanguageChanged;

  const _TranslationControls({
    required this.sourceType,
    required this.targetLanguage,
    required this.hasSummary,
    required this.hasMinutes,
    required this.onSourceChanged,
    required this.onLanguageChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('번역 소스', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        SegmentedButton<String>(
          segments: [
            ButtonSegment<String>(
              value: 'summary',
              label: const Text('요약'),
              icon: const Icon(Icons.summarize_outlined),
              enabled: hasSummary,
            ),
            ButtonSegment<String>(
              value: 'minutes',
              label: const Text('회의록'),
              icon: const Icon(Icons.notes_outlined),
              enabled: hasMinutes,
            ),
          ],
          selected: {sourceType},
          onSelectionChanged: (values) => onSourceChanged(values.first),
        ),
        const SizedBox(height: 16),
        Text('대상 언어', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final option in _translationLanguageOptions)
              ChoiceChip(
                label: Text(option.label),
                selected: option.value == targetLanguage,
                onSelected: (_) => onLanguageChanged(option.value),
              ),
          ],
        ),
      ],
    );
  }
}

class _TranslationResultCard extends StatelessWidget {
  final TranslationResult translation;

  const _TranslationResultCard({required this.translation});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.translate_outlined),
                const SizedBox(width: 8),
                Text('번역 결과', style: Theme.of(context).textTheme.titleMedium),
                const Spacer(),
                if (translation.cached)
                  const Chip(
                    label: Text('캐시됨'),
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
            const SizedBox(height: 12),
            SelectableText(
              translation.translatedText,
              style: const TextStyle(height: 1.5),
            ),
          ],
        ),
      ),
    );
  }
}

class _TranslationSourceCard extends StatelessWidget {
  final TranslationResult translation;

  const _TranslationSourceCard({required this.translation});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.article_outlined),
                const SizedBox(width: 8),
                Text('원문 일부', style: Theme.of(context).textTheme.titleSmall),
                const Spacer(),
                Text(
                  translation.sourceType == 'summary' ? '요약' : '회의록',
                  style: Theme.of(context).textTheme.labelMedium,
                ),
              ],
            ),
            const SizedBox(height: 8),
            SelectableText(
              translation.sourceExcerpt,
              maxLines: 8,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _SalesContactBriefTab extends ConsumerWidget {
  final String? taskId;

  const _SalesContactBriefTab({required this.taskId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.business_center_outlined,
        title: '영업 브리프 준비 중',
        subtitle: '회의록이 완료되면 고객 니즈와 후속 조치를 정리합니다',
      );
    }

    final request = SalesContactBriefRequest(taskId: taskId!);
    final briefAsync = ref.watch(salesContactBriefProvider(request));

    return briefAsync.when(
      loading: () => const Padding(
        padding: EdgeInsets.all(16),
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(16),
            child: ShimmerText(lines: 6),
          ),
        ),
      ),
      error: (error, _) => ErrorRetryWidget(
        message: '영업 브리프를 불러올 수 없습니다',
        onRetry: () => ref.invalidate(salesContactBriefProvider(request)),
      ),
      data: (brief) {
        final hasContent = brief.customerNeeds.isNotEmpty ||
            brief.painPoints.isNotEmpty ||
            brief.objections.isNotEmpty ||
            brief.nextSteps.isNotEmpty ||
            brief.followUpMessage.trim().isNotEmpty;

        if (!hasContent) {
          return const SingleChildScrollView(
            padding: EdgeInsets.all(16),
            child: EmptyStateWidget(
              icon: Icons.business_center_outlined,
              title: '영업 브리프가 없습니다',
              subtitle: '고객 대화 내용이 충분하지 않아 후속 브리프를 만들 수 없습니다',
            ),
          );
        }

        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SalesContactHeader(brief: brief),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    OutlinedButton.icon(
                      onPressed: () => _copySalesBrief(context, brief),
                      icon: const Icon(Icons.copy_all_outlined),
                      label: const Text('브리프 복사'),
                    ),
                    FilledButton.tonalIcon(
                      onPressed: () => ref
                          .read(salesContactBriefProvider(request).notifier)
                          .regenerate(),
                      icon: const Icon(Icons.refresh_rounded),
                      label: const Text('다시 생성'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              _SalesBriefSection(
                icon: Icons.track_changes_outlined,
                title: '고객 니즈',
                items: brief.customerNeeds,
              ),
              _SalesBriefSection(
                icon: Icons.report_problem_outlined,
                title: 'Pain Points',
                items: brief.painPoints,
              ),
              _SalesBriefSection(
                icon: Icons.help_outline_rounded,
                title: 'Objections',
                items: brief.objections,
              ),
              if (brief.nextSteps.isNotEmpty) ...[
                Row(
                  children: [
                    const Icon(Icons.task_alt_outlined),
                    const SizedBox(width: 8),
                    Text('다음 액션',
                        style: Theme.of(context).textTheme.titleMedium),
                    const Spacer(),
                    Text('${brief.nextSteps.length}개'),
                  ],
                ),
                const SizedBox(height: 12),
                ...brief.nextSteps
                    .map((step) => _SalesNextStepCard(step: step)),
                const SizedBox(height: 12),
              ],
              if (brief.followUpMessage.trim().isNotEmpty)
                _SalesFollowUpCard(message: brief.followUpMessage),
            ],
          ),
        );
      },
    );
  }

  Future<void> _copySalesBrief(
    BuildContext context,
    SalesContactBrief brief,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    final buffer = StringBuffer()
      ..writeln('영업 브리프')
      ..writeln('---')
      ..writeln('고객: ${_displayContactName(brief.contact)}')
      ..writeln('딜 단계: ${brief.deal.stage}')
      ..writeln('긴급도: ${brief.deal.urgency}');

    void writeList(String title, List<String> items) {
      if (items.isEmpty) return;
      buffer.writeln();
      buffer.writeln(title);
      for (var index = 0; index < items.length; index++) {
        buffer.writeln('${index + 1}. ${items[index]}');
      }
    }

    writeList('고객 니즈', brief.customerNeeds);
    writeList('Pain Points', brief.painPoints);
    writeList('Objections', brief.objections);

    if (brief.nextSteps.isNotEmpty) {
      buffer.writeln();
      buffer.writeln('다음 액션');
      for (var index = 0; index < brief.nextSteps.length; index++) {
        final step = brief.nextSteps[index];
        final meta = [
          if ((step.owner ?? '').isNotEmpty) step.owner,
          if ((step.due ?? '').isNotEmpty) step.due,
        ].join(' · ');
        buffer.writeln(
          '${index + 1}. ${step.task}${meta.isEmpty ? '' : ' ($meta)'}',
        );
      }
    }

    if (brief.followUpMessage.trim().isNotEmpty) {
      buffer.writeln();
      buffer.writeln('후속 메시지');
      buffer.writeln(brief.followUpMessage);
    }

    await Clipboard.setData(ClipboardData(text: buffer.toString()));
    messenger.showSnackBar(
      const SnackBar(content: Text('영업 브리프를 복사했습니다')),
    );
  }
}

class _SalesContactHeader extends StatelessWidget {
  final SalesContactBrief brief;

  const _SalesContactHeader({required this.brief});

  @override
  Widget build(BuildContext context) {
    final contact = brief.contact;
    final hasEmail = (contact.email ?? '').trim().isNotEmpty;
    final hasPhone = (contact.phone ?? '').trim().isNotEmpty;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.person_search_outlined),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('연락처 확인',
                          style: Theme.of(context).textTheme.labelLarge),
                      Text(
                        _displayContactName(contact),
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ],
                  ),
                ),
                Chip(
                  label: Text(brief.deal.stage),
                  visualDensity: VisualDensity.compact,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: OutlinedButton.icon(
                onPressed: () => _copyContactSummary(context, contact),
                icon: const Icon(Icons.contact_page_outlined),
                label: const Text('연락처 복사'),
              ),
            ),
            const SizedBox(height: 12),
            _ContactFieldRow(
              icon: Icons.business_outlined,
              label: '회사',
              value: contact.company,
            ),
            _ContactFieldRow(
              icon: Icons.work_outline_rounded,
              label: '직함',
              value: contact.role,
            ),
            _ContactFieldRow(
              icon: Icons.mail_outline_rounded,
              label: '이메일',
              value: contact.email,
              onCopy: hasEmail
                  ? () => _copyContactValue(context, '이메일', contact.email!)
                  : null,
            ),
            _ContactFieldRow(
              icon: Icons.phone_outlined,
              label: '전화',
              value: contact.phone,
              onCopy: hasPhone
                  ? () => _copyContactValue(context, '전화', contact.phone!)
                  : null,
            ),
            if (!hasEmail || !hasPhone) ...[
              const SizedBox(height: 8),
              Text(
                '비어 있는 필드는 원본 명함/대화 내용을 확인해 보완하세요.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                Chip(
                  avatar: const Icon(Icons.bolt_outlined, size: 18),
                  label: Text('긴급도 ${brief.deal.urgency}'),
                  visualDensity: VisualDensity.compact,
                ),
                if ((brief.deal.valueHint ?? '').isNotEmpty)
                  Chip(
                    avatar: const Icon(Icons.payments_outlined, size: 18),
                    label: Text(brief.deal.valueHint!),
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _copyContactSummary(
    BuildContext context,
    SalesContactIdentity contact,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    final buffer = StringBuffer()
      ..writeln('연락처')
      ..writeln(
          '이름: ${contact.name?.trim().isNotEmpty == true ? contact.name!.trim() : '미확인'}');

    void writeField(String label, String? value) {
      final normalized = value?.trim() ?? '';
      if (normalized.isEmpty) return;
      buffer.writeln('$label: $normalized');
    }

    writeField('회사', contact.company);
    writeField('직함', contact.role);
    writeField('이메일', contact.email);
    writeField('전화', contact.phone);

    await Clipboard.setData(ClipboardData(text: buffer.toString()));
    messenger.showSnackBar(
      const SnackBar(content: Text('연락처를 복사했습니다')),
    );
  }

  Future<void> _copyContactValue(
    BuildContext context,
    String label,
    String value,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    await Clipboard.setData(ClipboardData(text: value.trim()));
    messenger.showSnackBar(
      SnackBar(content: Text('$label을 복사했습니다')),
    );
  }
}

class _ContactFieldRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? value;
  final VoidCallback? onCopy;

  const _ContactFieldRow({
    required this.icon,
    required this.label,
    required this.value,
    this.onCopy,
  });

  @override
  Widget build(BuildContext context) {
    final normalized = value?.trim() ?? '';
    final displayValue = normalized.isEmpty ? '미확인' : normalized;
    final colors = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(icon, size: 18, color: colors.onSurfaceVariant),
          const SizedBox(width: 8),
          SizedBox(
            width: 54,
            child: Text(label, style: Theme.of(context).textTheme.labelMedium),
          ),
          Expanded(
            child: SelectableText(
              displayValue,
              maxLines: 1,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: normalized.isEmpty ? colors.onSurfaceVariant : null,
                  ),
            ),
          ),
          if (onCopy != null)
            IconButton(
              tooltip: '$label 복사',
              icon: const Icon(Icons.copy_outlined, size: 18),
              onPressed: onCopy,
            ),
        ],
      ),
    );
  }
}

class _SalesBriefSection extends StatelessWidget {
  final IconData icon;
  final String title;
  final List<String> items;

  const _SalesBriefSection({
    required this.icon,
    required this.title,
    required this.items,
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon),
              const SizedBox(width: 8),
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              Text('${items.length}개'),
            ],
          ),
          const SizedBox(height: 12),
          ...items.map(
            (item) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                dense: true,
                leading: const Icon(Icons.check_circle_outline_rounded),
                title: Text(item),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SalesNextStepCard extends StatelessWidget {
  final SalesNextStep step;

  const _SalesNextStepCard({required this.step});

  @override
  Widget build(BuildContext context) {
    final meta = [
      if ((step.owner ?? '').isNotEmpty) step.owner!,
      if ((step.due ?? '').isNotEmpty) step.due!,
    ].join(' · ');

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: const Icon(Icons.task_alt_outlined),
        title: Text(step.task),
        subtitle: meta.isEmpty ? null : Text(meta),
      ),
    );
  }
}

class _SalesFollowUpCard extends StatelessWidget {
  final String message;

  const _SalesFollowUpCard({required this.message});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.forward_to_inbox_outlined),
                const SizedBox(width: 8),
                Text('후속 메시지', style: Theme.of(context).textTheme.titleMedium),
              ],
            ),
            const SizedBox(height: 12),
            SelectableText(message, style: const TextStyle(height: 1.5)),
          ],
        ),
      ),
    );
  }
}

String _displayContactName(SalesContactIdentity contact) {
  final name = contact.name?.trim();
  if (name != null && name.isNotEmpty) return name;
  final company = contact.company?.trim();
  if (company != null && company.isNotEmpty) return company;
  return '고객 미확인';
}

class _StudyModeOption {
  final String value;
  final String label;

  const _StudyModeOption(this.value, this.label);
}

const _studyModeOptions = [
  _StudyModeOption('lecture', '강의'),
  _StudyModeOption('meeting', '회의'),
  _StudyModeOption('interview', '인터뷰'),
  _StudyModeOption('sermon', '설교'),
  _StudyModeOption('general', '일반'),
];

class _StudyTab extends ConsumerStatefulWidget {
  final String? taskId;

  const _StudyTab({required this.taskId});

  @override
  ConsumerState<_StudyTab> createState() => _StudyTabState();
}

class _StudyTabState extends ConsumerState<_StudyTab> {
  String _selectedMode = 'lecture';

  @override
  Widget build(BuildContext context) {
    if (widget.taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.school_outlined,
        title: '학습 자료 준비 중',
        subtitle: '회의록이 완료되면 플래시카드와 퀴즈가 생성됩니다',
      );
    }

    final request = StudyPackRequest(
      taskId: widget.taskId!,
      mode: _selectedMode,
    );
    final studyPackAsync = ref.watch(studyPackProvider(request));

    return studyPackAsync.when(
      loading: () => const Padding(
        padding: EdgeInsets.all(16),
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(16),
            child: ShimmerText(lines: 6),
          ),
        ),
      ),
      error: (error, _) => ErrorRetryWidget(
        message: '학습 자료를 불러올 수 없습니다',
        onRetry: () => ref.invalidate(studyPackProvider(request)),
      ),
      data: (pack) {
        if (pack.keyConcepts.isEmpty &&
            pack.flashcards.isEmpty &&
            pack.quizQuestions.isEmpty &&
            pack.studyNotes.trim().isEmpty) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                _StudyModeSelector(
                  selectedMode: _selectedMode,
                  onChanged: _setStudyMode,
                ),
                const SizedBox(height: 16),
                const EmptyStateWidget(
                  icon: Icons.school_outlined,
                  title: '학습 자료가 없습니다',
                  subtitle: '회의록 내용이 충분하지 않아 학습팩을 만들 수 없습니다',
                ),
              ],
            ),
          );
        }

        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _StudyModeSelector(
                selectedMode: _selectedMode,
                onChanged: _setStudyMode,
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    OutlinedButton.icon(
                      onPressed: () => _copyStudyMaterials(context, pack),
                      icon: const Icon(Icons.copy_all_outlined),
                      label: const Text('학습팩 복사'),
                    ),
                    FilledButton.tonalIcon(
                      onPressed: () => ref
                          .read(studyPackProvider(request).notifier)
                          .regenerate(),
                      icon: const Icon(Icons.refresh_rounded),
                      label: const Text('다시 생성'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              if (pack.studyNotes.trim().isNotEmpty) ...[
                _StudyNotesCard(notes: pack.studyNotes),
                const SizedBox(height: 24),
              ],
              if (pack.keyConcepts.isNotEmpty) ...[
                Row(
                  children: [
                    const Icon(Icons.lightbulb_outline_rounded),
                    const SizedBox(width: 8),
                    Text(
                      '핵심 개념',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const Spacer(),
                    Text('${pack.keyConcepts.length}개'),
                  ],
                ),
                const SizedBox(height: 12),
                ...pack.keyConcepts.map((concept) => _StudyConceptCard(
                      concept: concept,
                      sourceRefs: pack.sourceRefs,
                    )),
                const SizedBox(height: 24),
              ],
              Row(
                children: [
                  const Icon(Icons.school_outlined),
                  const SizedBox(width: 8),
                  Text(
                    '플래시카드',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const Spacer(),
                  Text('${pack.flashcards.length}개'),
                ],
              ),
              const SizedBox(height: 12),
              ...pack.flashcards.map(
                (card) => _StudyFlashcard(
                  card: card,
                  sourceRefs: pack.sourceRefs,
                ),
              ),
              if (pack.flashcards.isNotEmpty) const SizedBox(height: 24),
              Row(
                children: [
                  const Icon(Icons.quiz_outlined),
                  const SizedBox(width: 8),
                  Text(
                    '복습 퀴즈',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const Spacer(),
                  Text('${pack.quizQuestions.length}문항'),
                ],
              ),
              const SizedBox(height: 12),
              ...pack.quizQuestions.asMap().entries.map(
                    (entry) => _StudyQuizCard(
                      index: entry.key + 1,
                      quiz: entry.value,
                      sourceRefs: pack.sourceRefs,
                    ),
                  ),
            ],
          ),
        );
      },
    );
  }

  void _setStudyMode(String mode) {
    if (mode == _selectedMode) return;
    setState(() => _selectedMode = mode);
  }

  Future<void> _copyStudyMaterials(
    BuildContext context,
    StudyPack pack,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    final buffer = StringBuffer()
      ..writeln('학습팩')
      ..writeln('---');

    if (pack.studyNotes.trim().isNotEmpty) {
      buffer.writeln();
      buffer.writeln('학습 노트');
      buffer.writeln(pack.studyNotes);
    }

    if (pack.keyConcepts.isNotEmpty) {
      buffer.writeln();
      buffer.writeln('핵심 개념');
      for (var index = 0; index < pack.keyConcepts.length; index++) {
        final concept = pack.keyConcepts[index];
        buffer.writeln('${index + 1}. ${concept.term}: ${concept.explanation}');
      }
    }

    if (pack.flashcards.isNotEmpty) {
      buffer.writeln();
      buffer.writeln('플래시카드');
      for (var index = 0; index < pack.flashcards.length; index++) {
        final card = pack.flashcards[index];
        buffer.writeln('${index + 1}. ${card.front}');
        buffer.writeln('   답: ${card.back}');
      }
    }

    if (pack.quizQuestions.isNotEmpty) {
      buffer.writeln();
      buffer.writeln('복습 퀴즈');
      for (var index = 0; index < pack.quizQuestions.length; index++) {
        final quiz = pack.quizQuestions[index];
        buffer.writeln('${index + 1}. ${quiz.question}');
        buffer.writeln('   정답: ${quiz.answer}');
      }
    }

    await Clipboard.setData(ClipboardData(text: buffer.toString()));
    messenger.showSnackBar(
      const SnackBar(content: Text('학습팩을 복사했습니다')),
    );
  }
}

class _StudyModeSelector extends StatelessWidget {
  final String selectedMode;
  final ValueChanged<String> onChanged;

  const _StudyModeSelector({
    required this.selectedMode,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final option in _studyModeOptions)
          ChoiceChip(
            label: Text(option.label),
            selected: option.value == selectedMode,
            onSelected: (_) => onChanged(option.value),
          ),
      ],
    );
  }
}

class _StudyNotesCard extends StatelessWidget {
  final String notes;

  const _StudyNotesCard({required this.notes});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.menu_book_outlined),
                const SizedBox(width: 8),
                Text('학습 노트', style: Theme.of(context).textTheme.titleMedium),
              ],
            ),
            const SizedBox(height: 12),
            Text(notes, style: const TextStyle(height: 1.5)),
          ],
        ),
      ),
    );
  }
}

class _StudyConceptCard extends StatelessWidget {
  final StudyKeyConcept concept;
  final List<StudySourceRef> sourceRefs;

  const _StudyConceptCard({
    required this.concept,
    required this.sourceRefs,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: const Icon(Icons.lightbulb_outline_rounded),
        title: Text(concept.term),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(concept.explanation),
            _SourceRefText(indexes: concept.sourceRefs, sourceRefs: sourceRefs),
          ],
        ),
      ),
    );
  }
}

class _StudyFlashcard extends StatelessWidget {
  final StudyFlashcard card;
  final List<StudySourceRef> sourceRefs;

  const _StudyFlashcard({
    required this.card,
    required this.sourceRefs,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Chip(
              avatar: Icon(Icons.style_outlined, size: 18),
              label: Text('플래시카드'),
            ),
            const SizedBox(height: 8),
            Text(
              card.front,
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            Text(card.back, style: const TextStyle(height: 1.5)),
            _SourceRefText(indexes: card.sourceRefs, sourceRefs: sourceRefs),
          ],
        ),
      ),
    );
  }
}

class _StudyQuizCard extends StatelessWidget {
  final int index;
  final StudyQuizQuestion quiz;
  final List<StudySourceRef> sourceRefs;

  const _StudyQuizCard({
    required this.index,
    required this.quiz,
    required this.sourceRefs,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        leading: CircleAvatar(child: Text('$index')),
        title: Text(quiz.question),
        subtitle: Text('난이도: ${quiz.difficulty}'),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              '정답: ${quiz.answer}',
              style: const TextStyle(height: 1.5),
            ),
          ),
          _SourceRefText(indexes: quiz.sourceRefs, sourceRefs: sourceRefs),
        ],
      ),
    );
  }
}

class _SourceRefText extends StatelessWidget {
  final List<int> indexes;
  final List<StudySourceRef> sourceRefs;

  const _SourceRefText({
    required this.indexes,
    required this.sourceRefs,
  });

  @override
  Widget build(BuildContext context) {
    if (indexes.isEmpty || sourceRefs.isEmpty) {
      return const SizedBox.shrink();
    }

    final labels = indexes
        .map((index) =>
            sourceRefs.where((ref) => ref.segmentIndex == index).firstOrNull)
        .whereType<StudySourceRef>()
        .map((ref) {
          final speaker = ref.speaker == null ? '' : '${ref.speaker} ';
          final time =
              ref.start == null ? '' : '@${ref.start!.toStringAsFixed(0)}s';
          return '$speaker$time'.trim();
        })
        .where((label) => label.isNotEmpty)
        .toList();

    if (labels.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Text(
        '근거: ${labels.join(', ')}',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppColors.of(context).textSecondary,
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

class _PromiseRadarTab extends ConsumerWidget {
  final String? taskId;

  const _PromiseRadarTab({required this.taskId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (taskId == null) {
      return const EmptyStateWidget(
        icon: Icons.track_changes_outlined,
        title: '약속 레이더 준비 중',
        subtitle: '요약 처리가 완료되면 과거 회의와 약속을 비교합니다',
      );
    }

    final radarAsync = ref.watch(promiseRadarProvider(taskId!));
    return radarAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => ErrorRetryWidget(
        message: '약속 레이더를 불러올 수 없습니다',
        onRetry: () => ref.invalidate(promiseRadarProvider(taskId!)),
      ),
      data: (radar) => RefreshIndicator(
        onRefresh: () async => ref.invalidate(promiseRadarProvider(taskId!)),
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.md),
          children: [
            _buildHeader(context, radar),
            if (radar.nextMeetingBriefing != null) ...[
              const SizedBox(height: AppSpacing.md),
              _buildNextBriefingSection(context, radar.nextMeetingBriefing!),
            ],
            if (radar.nextMeetingBriefing?.responsibilityScores.isNotEmpty ??
                false) ...[
              const SizedBox(height: AppSpacing.md),
              _buildResponsibilityScoreSection(
                context,
                radar.nextMeetingBriefing!.responsibilityScores,
              ),
            ],
            if (radar.nextMeetingBriefing?.meetingSeries.isNotEmpty ??
                false) ...[
              const SizedBox(height: AppSpacing.md),
              _buildMeetingSeriesSection(
                context,
                radar.nextMeetingBriefing!.meetingSeries,
              ),
            ],
            if (radar.ledgerEntries.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              _buildLedgerSection(context, ref, radar.ledgerEntries, taskId!),
            ],
            if (radar.ownerRisks.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              _buildOwnerRiskSection(context, radar.ownerRisks),
            ],
            if (radar.promiseChains.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              _buildPromiseChainSection(context, radar.promiseChains),
            ],
            const SizedBox(height: AppSpacing.md),
            if (radar.followUpQuestions.isNotEmpty)
              _buildQuestionSection(context, radar.followUpQuestions),
            if (radar.stalePromises.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              _buildPromiseSection(
                context,
                title: '미확인 과거 약속',
                icon: Icons.report_problem_outlined,
                items: radar.stalePromises,
              ),
            ],
            if (radar.carriedOverPromises.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              _buildCarryOverSection(context, radar.carriedOverPromises),
            ],
            if (radar.decisionDrifts.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              _buildDecisionDriftSection(context, radar.decisionDrifts),
            ],
            const SizedBox(height: AppSpacing.md),
            _buildPromiseSection(
              context,
              title: '이번 회의의 새 약속',
              icon: Icons.add_task_outlined,
              items: radar.currentPromises,
              emptyText: '이번 회의에서 구조화된 새 약속을 찾지 못했습니다.',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, PromiseRadarResult radar) {
    final theme = Theme.of(context);
    final color = _riskColor(radar.riskScore, theme.colorScheme);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.track_changes_outlined, color: color),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    '약속 레이더',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                Text(
                  '${radar.riskScore}%',
                  style: theme.textTheme.titleLarge?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: radar.riskScore / 100,
                minHeight: 8,
                color: color,
                backgroundColor: theme.colorScheme.surfaceContainerHighest,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            Text(radar.headline, style: theme.textTheme.bodyMedium),
            const SizedBox(height: AppSpacing.sm),
            Text(
              '분석한 회의 ${radar.analyzedMeetings}개 · 새 약속 ${radar.currentPromises.length}개 · 미확인 ${radar.stalePromises.length}개 · 고위험 ${radar.highRiskCount}개',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNextBriefingSection(
    BuildContext context,
    PromiseNextMeetingBriefing briefing,
  ) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(
                context, Icons.event_available_outlined, briefing.title),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.xs,
              children: [
                _PromiseMetricPill(
                    label: '고위험', value: '${briefing.highRiskCount}'),
                _PromiseMetricPill(
                    label: '기한 초과', value: '${briefing.overdueCount}'),
                _PromiseMetricPill(
                    label: '3일 내', value: '${briefing.dueSoonCount}'),
              ],
            ),
            if (briefing.questions.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              for (final question in briefing.questions.take(3))
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        Icons.question_answer_outlined,
                        size: 16,
                        color: theme.colorScheme.primary,
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      Expanded(child: Text(question)),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildResponsibilityScoreSection(
    BuildContext context,
    List<PromiseResponsibilityScore> scores,
  ) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(context, Icons.speed_outlined, '담당자 책임 점수'),
            const SizedBox(height: AppSpacing.sm),
            for (final score in scores.take(5))
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            score.owner,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        _RiskChip(level: score.riskLevel),
                        const SizedBox(width: AppSpacing.xs),
                        Text(
                          '${score.score}%',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: _riskColor(score.score, theme.colorScheme),
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      '열림 ${score.openCount} · 완료 ${score.completedCount} · 기한 초과 ${score.overdueCount} · 완료율 ${_percentageLabel(score.completionRate)}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    if (score.reasons.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        score.reasons.take(3).join(' / '),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildMeetingSeriesSection(
    BuildContext context,
    List<PromiseMeetingSeries> series,
  ) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(context, Icons.hub_outlined, '반복회의 연결'),
            const SizedBox(height: AppSpacing.sm),
            for (final item in series.take(4))
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            item.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        _PromiseMetricPill(
                          label: '회의',
                          value: '${item.meetingCount}',
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      '열린 약속 ${item.openCount}개 · 기한 초과 ${item.overdueCount}개 · 고위험 ${item.highRiskCount}개',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    if (item.owners.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        '담당자 ${item.owners.take(3).join(', ')}',
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                    if (item.nextQuestions.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        item.nextQuestions.first,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildLedgerSection(
    BuildContext context,
    WidgetRef ref,
    List<PromiseLedgerEntry> entries,
    String summaryTaskId,
  ) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: _sectionTitle(
                      context, Icons.fact_check_outlined, '약속 원장'),
                ),
                IconButton(
                  tooltip: '자동화 정책',
                  onPressed: () => _showAutomationPolicySheet(context, ref),
                  icon: const Icon(Icons.rule_folder_outlined),
                ),
                IconButton(
                  tooltip: 'Digest 설정',
                  onPressed: () => _showDigestPreferenceSheet(context, ref),
                  icon: const Icon(Icons.notifications_outlined),
                ),
                IconButton(
                  tooltip: '회의 전 브리프 푸시',
                  onPressed: () => _dispatchPreMeetingBrief(
                    context,
                    ref,
                    summaryTaskId,
                  ),
                  icon: const Icon(Icons.campaign_outlined),
                ),
                IconButton(
                  tooltip: 'Promise Radar 정확도',
                  onPressed: () => _showAccuracyReportSheet(context, ref),
                  icon: const Icon(Icons.analytics_outlined),
                ),
                OutlinedButton.icon(
                  onPressed: () => _runAutopilot(context, ref, summaryTaskId),
                  icon: const Icon(Icons.auto_fix_high_outlined, size: 18),
                  label: const Text('자동 판정'),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            for (final entry in entries.take(6))
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    border: Border(
                      left: BorderSide(
                        color:
                            _riskLevelColor(entry.riskLevel, theme.colorScheme),
                        width: 3,
                      ),
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.only(left: AppSpacing.sm),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                entry.text,
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            _StatusChip(status: entry.status),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.xs),
                        Text(
                          '${entry.owner ?? entry.speakerLabel ?? '담당자 미지정'} · ${entry.occurrences}회 추적'
                          '${entry.dueDate != null ? ' · ${entry.dueDate}' : ''}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                        if (entry.quality != null) ...[
                          const SizedBox(height: AppSpacing.xs),
                          Wrap(
                            spacing: AppSpacing.xs,
                            runSpacing: AppSpacing.xs,
                            children: [
                              _PromiseMetricPill(
                                label: '품질',
                                value: '${entry.quality!.score}%',
                              ),
                              if (entry.quality!.issues.isNotEmpty)
                                _PromiseMetricPill(
                                  label: '보강',
                                  value: '${entry.quality!.issues.length}',
                                ),
                              if (entry.identityConfidence != null)
                                _PromiseMetricPill(
                                  label: '화자',
                                  value:
                                      '${(entry.identityConfidence! * 100).round()}%',
                                ),
                            ],
                          ),
                          if (entry.quality!.issues.isNotEmpty) ...[
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              entry.quality!.issues.first,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.error,
                              ),
                            ),
                          ],
                        ],
                        if (entry.evidence.isNotEmpty) ...[
                          const SizedBox(height: AppSpacing.xs),
                          Text(
                            _evidenceLabel(entry.evidence.first),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.bodySmall,
                          ),
                        ],
                        if (_hasGoogleTaskLink(entry)) ...[
                          const SizedBox(height: AppSpacing.xs),
                          Text(
                            _googleTaskLinkLabel(entry),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.primary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                        const SizedBox(height: AppSpacing.xs),
                        Wrap(
                          spacing: AppSpacing.xs,
                          children: [
                            TextButton.icon(
                              onPressed: () => _updateLedgerStatus(
                                context,
                                ref,
                                summaryTaskId,
                                entry.id,
                                'completed',
                              ),
                              icon: const Icon(Icons.check_circle_outline,
                                  size: 18),
                              label: const Text('완료'),
                            ),
                            TextButton.icon(
                              onPressed: () => _updateLedgerStatus(
                                context,
                                ref,
                                summaryTaskId,
                                entry.id,
                                'blocked',
                              ),
                              icon: const Icon(Icons.block_outlined, size: 18),
                              label: const Text('차단'),
                            ),
                            TextButton.icon(
                              onPressed: () => _updateLedgerStatus(
                                context,
                                ref,
                                summaryTaskId,
                                entry.id,
                                entry.status,
                                userConfirmed: true,
                              ),
                              icon:
                                  const Icon(Icons.verified_outlined, size: 18),
                              label: const Text('맞음'),
                            ),
                            TextButton.icon(
                              onPressed: entry.actionItemId == null
                                  ? () => _createActionItem(
                                        context,
                                        ref,
                                        summaryTaskId,
                                        entry.id,
                                      )
                                  : null,
                              icon:
                                  const Icon(Icons.add_task_outlined, size: 18),
                              label: Text(
                                  entry.actionItemId == null ? '할 일' : '연결됨'),
                            ),
                            TextButton.icon(
                              onPressed: entries.length > 1
                                  ? () => _showMergeLedgerDialog(
                                        context,
                                        ref,
                                        summaryTaskId,
                                        entry,
                                        entries,
                                      )
                                  : null,
                              icon: const Icon(Icons.merge_type_outlined,
                                  size: 18),
                              label: const Text('병합'),
                            ),
                            TextButton.icon(
                              onPressed: () => _showSplitLedgerDialog(
                                context,
                                ref,
                                summaryTaskId,
                                entry,
                              ),
                              icon: const Icon(Icons.call_split_outlined,
                                  size: 18),
                              label: const Text('분리'),
                            ),
                            TextButton.icon(
                              onPressed: () => _createReminderCandidate(
                                context,
                                ref,
                                summaryTaskId,
                                entry.id,
                              ),
                              icon: const Icon(
                                  Icons.notifications_active_outlined,
                                  size: 18),
                              label:
                                  Text(entry.reminderAt == null ? '알림' : '알림됨'),
                            ),
                            TextButton.icon(
                              onPressed: () => _exportCalendarEvent(
                                context,
                                ref,
                                summaryTaskId,
                                entry.id,
                              ),
                              icon: const Icon(Icons.event_outlined, size: 18),
                              label: const Text('캘린더'),
                            ),
                            TextButton.icon(
                              onPressed: () => _showMatchExplanation(
                                context,
                                ref,
                                summaryTaskId,
                                entry.id,
                              ),
                              icon: const Icon(Icons.psychology_alt_outlined,
                                  size: 18),
                              label: const Text('근거'),
                            ),
                            TextButton.icon(
                              onPressed: () => _showLatestEvidencePack(
                                context,
                                ref,
                                entry.id,
                              ),
                              icon: const Icon(
                                Icons.travel_explore_outlined,
                                size: 18,
                              ),
                              label: const Text('증거팩'),
                            ),
                            TextButton.icon(
                              onPressed: () => _showEvidenceComparison(
                                context,
                                ref,
                                entry.id,
                              ),
                              icon: const Icon(
                                Icons.compare_arrows_outlined,
                                size: 18,
                              ),
                              label: const Text('근거 비교'),
                            ),
                            TextButton.icon(
                              onPressed: () => _showAssigneeSuggestions(
                                context,
                                ref,
                                entry.id,
                              ),
                              icon: const Icon(Icons.person_search_outlined,
                                  size: 18),
                              label: const Text('담당자'),
                            ),
                            TextButton.icon(
                              onPressed: () => _showLedgerHistory(
                                context,
                                ref,
                                entry.id,
                              ),
                              icon:
                                  const Icon(Icons.history_outlined, size: 18),
                              label: const Text('이력'),
                            ),
                            TextButton.icon(
                              onPressed: () => _showLedgerTimeline(
                                context,
                                ref,
                                entry.id,
                              ),
                              icon:
                                  const Icon(Icons.timeline_outlined, size: 18),
                              label: const Text('타임라인'),
                            ),
                            TextButton.icon(
                              onPressed: () => _recordLearningFeedback(
                                context,
                                ref,
                                summaryTaskId,
                                entry,
                              ),
                              icon: const Icon(Icons.school_outlined, size: 18),
                              label: const Text('오판'),
                            ),
                            TextButton.icon(
                              onPressed: () => _exportSlackTaskPreview(
                                context,
                                ref,
                                entry.id,
                              ),
                              icon: const Icon(Icons.send_outlined, size: 18),
                              label: const Text('Slack'),
                            ),
                            TextButton.icon(
                              onPressed: () => _exportGoogleTask(
                                context,
                                ref,
                                summaryTaskId,
                                entry.id,
                              ),
                              icon:
                                  const Icon(Icons.task_alt_outlined, size: 18),
                              label: const Text('Tasks'),
                            ),
                            TextButton.icon(
                              onPressed: _hasGoogleTaskLink(entry)
                                  ? () => _syncGoogleTask(
                                        context,
                                        ref,
                                        summaryTaskId,
                                        entry,
                                      )
                                  : null,
                              icon: const Icon(Icons.sync_outlined, size: 18),
                              label: const Text('Tasks 동기화'),
                            ),
                            TextButton.icon(
                              onPressed: _hasGoogleTaskLink(entry)
                                  ? () => _updateGoogleTaskFromLedger(
                                        context,
                                        ref,
                                        summaryTaskId,
                                        entry,
                                      )
                                  : null,
                              icon: const Icon(Icons.upload_outlined, size: 18),
                              label: const Text('Tasks 업데이트'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildOwnerRiskSection(
    BuildContext context,
    List<PromiseRadarOwnerRisk> owners,
  ) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(context, Icons.person_search_outlined, '담당자별 약속 리스크'),
            const SizedBox(height: AppSpacing.sm),
            for (final owner in owners.take(6))
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            owner.owner,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        Text(
                          '${owner.riskScore}%',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color:
                                _riskColor(owner.riskScore, theme.colorScheme),
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      '열린 약속 ${owner.openPromises}개 · 미확인 ${owner.stalePromises}개 · 반복 ${owner.recurringPromises}개',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    if (owner.latestPromises.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        owner.latestPromises.take(2).join(' / '),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildPromiseChainSection(
    BuildContext context,
    List<PromiseRadarPromiseChain> chains,
  ) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(context, Icons.timeline_outlined, '회의를 넘어 이어진 약속 체인'),
            const SizedBox(height: AppSpacing.sm),
            for (final chain in chains.take(6))
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            chain.canonicalText,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        _RiskChip(level: chain.riskLevel),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      '${chain.occurrences}회 등장 · ${chain.ageDays}일 경과 · ${_chainStatusLabel(chain.status)}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    if (chain.links.length > 1) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        chain.links
                            .take(3)
                            .map((link) => link.text)
                            .join(' → '),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuestionSection(BuildContext context, List<String> questions) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(context, Icons.help_outline, '다음 회의에서 바로 확인할 질문'),
            const SizedBox(height: AppSpacing.sm),
            for (final question in questions)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.xs),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('• ', style: theme.textTheme.bodyMedium),
                    Expanded(child: Text(question)),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildPromiseSection(
    BuildContext context, {
    required String title,
    required IconData icon,
    required List<PromiseRadarPromise> items,
    String emptyText = '표시할 약속이 없습니다.',
  }) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(context, icon, title),
            const SizedBox(height: AppSpacing.sm),
            if (items.isEmpty)
              Text(
                emptyText,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              )
            else
              for (final item in items) _PromiseTile(item: item),
          ],
        ),
      ),
    );
  }

  Widget _buildCarryOverSection(
    BuildContext context,
    List<PromiseRadarCarryOver> items,
  ) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(context, Icons.loop_rounded, '반복 등장한 약속'),
            const SizedBox(height: AppSpacing.sm),
            for (final item in items)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(item.current.text,
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      '이전 표현: ${item.previous.text}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
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

  Widget _buildDecisionDriftSection(
    BuildContext context,
    List<PromiseRadarDecisionDrift> items,
  ) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(context, Icons.compare_arrows_rounded, '결정 변경 후보'),
            const SizedBox(height: AppSpacing.sm),
            for (final item in items)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('현재: ${item.currentDecision}',
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      '이전: ${item.previousDecision}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
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

  Widget _sectionTitle(BuildContext context, IconData icon, String title) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Icon(icon, size: 20, color: theme.colorScheme.primary),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            title,
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }

  Color _riskColor(int score, ColorScheme scheme) {
    if (score >= 70) return scheme.error;
    if (score >= 35) return AppColors.warning;
    return AppColors.success;
  }

  Color _riskLevelColor(String level, ColorScheme scheme) {
    return switch (level) {
      'critical' => scheme.error,
      'high' => scheme.error,
      'medium' => AppColors.warning,
      _ => AppColors.success,
    };
  }

  String _chainStatusLabel(String status) {
    return switch (status) {
      'recurring' => '반복 추적 중',
      'stale' => '현재 회의에서 미확인',
      _ => '현재 활성',
    };
  }

  String _statusLabel(String status) {
    return switch (status) {
      'completed' => '완료',
      'dismissed' => '제외',
      'delegated' => '위임',
      'blocked' => '차단',
      'delayed' => '지연',
      'changed' => '변경',
      _ => '진행',
    };
  }

  String _percentageLabel(num value) => '${(value * 100).round()}%';

  String _automationPolicyLabel(String mode) {
    return switch (mode) {
      'preview_only' => '항상 미리보기',
      'completed_only' => '완료만 자동 적용',
      'manual_only' => '모든 판정 수동 확인',
      _ => '안전 자동 적용',
    };
  }

  String _digestCadenceLabel(String cadence) {
    return switch (cadence) {
      'weekly' => 'Weekly Digest',
      _ => 'Daily Digest',
    };
  }

  bool _hasGoogleTaskLink(PromiseLedgerEntry entry) {
    return _googleTaskMetadata(entry)['external_id']?.isNotEmpty == true;
  }

  Map<String, String> _googleTaskMetadata(PromiseLedgerEntry entry) {
    final externalTasks = entry.calendarEvent?['external_tasks'];
    if (externalTasks is! Map<String, dynamic>) return const {};
    final googleTasks = externalTasks['google_tasks'];
    if (googleTasks is! Map<String, dynamic>) return const {};
    return googleTasks.map(
      (key, value) => MapEntry(key, value?.toString() ?? ''),
    );
  }

  String _googleTaskLinkLabel(PromiseLedgerEntry entry) {
    final metadata = _googleTaskMetadata(entry);
    final status = metadata['status']?.isNotEmpty == true
        ? _statusLabel(metadata['status']!)
        : '연결됨';
    final tasklist = metadata['tasklist']?.isNotEmpty == true
        ? metadata['tasklist']!
        : '@default';
    final externalId = metadata['external_id'] ?? '';
    final shortId = externalId.length > 12
        ? '${externalId.substring(0, 12)}...'
        : externalId;
    return [
      'Google Tasks $status',
      tasklist,
      if (shortId.isNotEmpty) shortId,
    ].join(' · ');
  }

  String _evidencePackAuditSummary(
    PromiseEvidencePack? pack,
    PromiseMatchExplanation? explanation,
  ) {
    final sourceTaskId = pack?.sourceTaskId ?? explanation?.matchedTaskId;
    final markerCount = pack?.markerHits.length ?? 0;
    final evidenceCount =
        pack?.evidence.length ?? explanation?.evidence.length ?? 0;
    final capturedAt = pack?.capturedAt;
    return [
      if (sourceTaskId != null && sourceTaskId.isNotEmpty)
        'source $sourceTaskId',
      'marker $markerCount',
      'evidence $evidenceCount',
      if (capturedAt != null && capturedAt.isNotEmpty) capturedAt,
    ].join(' · ');
  }

  String _evidenceLabel(PromiseRadarEvidence evidence) {
    final speaker = evidence.speaker ?? evidence.speakerLabel;
    final time = evidence.startSeconds != null
        ? '${evidence.startSeconds!.toStringAsFixed(1)}s'
        : null;
    final prefix = [
      if (speaker != null && speaker.isNotEmpty) speaker,
      if (time != null) time,
    ].join(' · ');
    return prefix.isEmpty
        ? evidence.transcript
        : '$prefix: ${evidence.transcript}';
  }

  Future<void> _showMergeLedgerDialog(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    PromiseLedgerEntry target,
    List<PromiseLedgerEntry> entries,
  ) async {
    final candidates = entries.where((entry) => entry.id != target.id).toList();
    final selected = <String>{};
    final noteController = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('약속 병합'),
          content: SizedBox(
            width: double.maxFinite,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  target.text,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: AppSpacing.sm),
                Flexible(
                  child: ListView(
                    shrinkWrap: true,
                    children: [
                      for (final entry in candidates)
                        CheckboxListTile(
                          value: selected.contains(entry.id),
                          onChanged: (checked) {
                            setState(() {
                              if (checked == true) {
                                selected.add(entry.id);
                              } else {
                                selected.remove(entry.id);
                              }
                            });
                          },
                          title: Text(
                            entry.text,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          subtitle: Text(
                              entry.owner ?? entry.speakerLabel ?? '담당자 미지정'),
                        ),
                    ],
                  ),
                ),
                TextField(
                  controller: noteController,
                  decoration: const InputDecoration(labelText: '메모'),
                  maxLines: 2,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: selected.isEmpty
                  ? null
                  : () => Navigator.of(dialogContext).pop(true),
              child: const Text('병합'),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true || selected.isEmpty) {
      noteController.dispose();
      return;
    }
    try {
      await ref.read(promiseRadarApiProvider).mergeLedgerEntries(
            target.id,
            sourceEntryIds: selected.toList(),
            note: noteController.text.trim().isEmpty
                ? null
                : noteController.text.trim(),
          );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseNextMeetingBriefingProvider);
      ref.invalidate(promiseRadarDashboardProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속이 병합됐습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 병합에 실패했습니다.')),
        );
      }
    } finally {
      noteController.dispose();
    }
  }

  Future<void> _showSplitLedgerDialog(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    PromiseLedgerEntry entry,
  ) async {
    final textController = TextEditingController(text: entry.text);
    final ownerController = TextEditingController(text: entry.owner ?? '');
    final dueController = TextEditingController(text: entry.dueDate ?? '');
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('약속 분리'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: textController,
              decoration: const InputDecoration(labelText: '새 약속 내용'),
              maxLines: 3,
            ),
            TextField(
              controller: ownerController,
              decoration: const InputDecoration(labelText: '담당자'),
            ),
            TextField(
              controller: dueController,
              decoration: const InputDecoration(labelText: '기한'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('분리'),
          ),
        ],
      ),
    );
    if (confirmed != true || textController.text.trim().isEmpty) {
      textController.dispose();
      ownerController.dispose();
      dueController.dispose();
      return;
    }
    try {
      await ref.read(promiseRadarApiProvider).splitLedgerEntry(
            entry.id,
            text: textController.text.trim(),
            owner: ownerController.text.trim().isEmpty
                ? null
                : ownerController.text.trim(),
            dueDate: dueController.text.trim().isEmpty
                ? null
                : dueController.text.trim(),
            priority: entry.priority,
          );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseNextMeetingBriefingProvider);
      ref.invalidate(promiseRadarDashboardProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속이 분리됐습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 분리에 실패했습니다.')),
        );
      }
    } finally {
      textController.dispose();
      ownerController.dispose();
      dueController.dispose();
    }
  }

  Future<void> _showLedgerHistory(
    BuildContext context,
    WidgetRef ref,
    String entryId,
  ) async {
    try {
      final history =
          await ref.read(promiseRadarApiProvider).listLedgerHistory(entryId);
      if (!context.mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        builder: (sheetContext) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              ListTile(
                leading: const Icon(Icons.history_outlined),
                title: const Text('약속 변경 이력'),
                subtitle: Text('${history.length}개 이벤트'),
              ),
              for (final item in history)
                ListTile(
                  title: Text(item.eventType),
                  subtitle: Text(item.note ?? item.createdAt),
                ),
            ],
          ),
        ),
      );
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 이력 조회에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _showLedgerTimeline(
    BuildContext context,
    WidgetRef ref,
    String entryId,
  ) async {
    try {
      final timeline =
          await ref.read(promiseRadarApiProvider).getTimeline(entryId);
      if (!context.mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        builder: (sheetContext) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              ListTile(
                leading: const Icon(Icons.timeline_outlined),
                title: const Text('약속 변경 타임라인'),
                subtitle: Text('현재 상태: ${timeline.currentStatus}'),
              ),
              for (final item in timeline.items)
                ListTile(
                  leading: const Icon(Icons.radio_button_checked, size: 16),
                  title: Text(item.label),
                  subtitle: Text(
                    [
                      item.createdAt,
                      if (item.statusBefore != null || item.statusAfter != null)
                        '${item.statusBefore ?? '-'} → ${item.statusAfter ?? '-'}',
                      if (item.confidence != null)
                        '신뢰도 ${(item.confidence! * 100).round()}%',
                      if (item.note != null) item.note!,
                    ].join(' · '),
                  ),
                ),
            ],
          ),
        ),
      );
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 타임라인 조회에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _recordLearningFeedback(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    PromiseLedgerEntry entry,
  ) async {
    try {
      final response =
          await ref.read(promiseRadarApiProvider).recordLearningFeedback(
                entry.id,
                PromiseLearningFeedbackRequest(
                  expectedStatus: 'open',
                  predictedStatus: entry.status,
                  expectedOwner: entry.owner,
                  correctionType: 'autopilot',
                  note: '완료 아님 또는 자동 판정 오판',
                ),
              );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseLearningProfileProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '학습 반영됨 · 자동 적용 기준 ${(response.learningProfile.autopilotThreshold * 100).round()}%',
            ),
          ),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('학습 피드백 저장에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _exportSlackTaskPreview(
    BuildContext context,
    WidgetRef ref,
    String entryId,
  ) async {
    try {
      final exported =
          await ref.read(promiseRadarApiProvider).exportExternalTask(
                entryId,
                const PromiseExternalExportRequest(provider: 'slack'),
              );
      await Clipboard.setData(
        ClipboardData(text: jsonEncode(exported.payload)),
      );
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Slack 전송 payload를 복사했습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Slack payload 생성에 실패했습니다.')),
        );
      }
    }
  }

  Future<String?> _requestGoogleTasksAccessToken(BuildContext context) async {
    if (!isGoogleSignInConfiguredForPlatform(isIOS: Platform.isIOS)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Google Tasks OAuth 설정이 필요합니다.')),
      );
      return null;
    }
    final googleSignIn = GoogleSignIn(
      clientId: googleClientIdForPlatform(
        isIOS: Platform.isIOS,
        isMacOS: Platform.isMacOS,
      ),
      serverClientId: googleServerClientId,
      scopes: ['email', 'profile', _googleTasksScope],
    );
    var account = await googleSignIn.signInSilently();
    account ??= await googleSignIn.signIn();
    if (account == null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Google Tasks 작업을 취소했습니다.')),
        );
      }
      return null;
    }
    final hasScope = await googleSignIn.canAccessScopes([_googleTasksScope]);
    final granted =
        hasScope || await googleSignIn.requestScopes([_googleTasksScope]);
    if (!granted) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Google Tasks 권한 승인이 필요합니다.')),
        );
      }
      return null;
    }
    final auth = await account.authentication;
    final accessToken = auth.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Google Tasks access token을 받을 수 없습니다.')),
        );
      }
      return null;
    }
    return accessToken;
  }

  Future<void> _exportGoogleTask(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    String entryId,
  ) async {
    try {
      final accessToken = await _requestGoogleTasksAccessToken(context);
      if (accessToken == null) return;
      final tasklists =
          await ref.read(promiseRadarApiProvider).listGoogleTaskLists(
                PromiseExternalExportRequest(
                  provider: 'google_tasks',
                  accessToken: accessToken,
                ),
              );
      if (!context.mounted) return;
      final selected =
          await _chooseGoogleTaskList(context, tasklists.tasklists);
      if (selected == null) return;
      final exported =
          await ref.read(promiseRadarApiProvider).exportExternalTask(
                entryId,
                PromiseExternalExportRequest(
                  provider: 'google_tasks',
                  dryRun: false,
                  accessToken: accessToken,
                  tasklist: selected.id,
                ),
              );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(exported.message)),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Google Tasks 전송에 실패했습니다.')),
        );
      }
    }
  }

  Future<PromiseGoogleTaskList?> _chooseGoogleTaskList(
    BuildContext context,
    List<PromiseGoogleTaskList> tasklists,
  ) async {
    final options = tasklists.isEmpty
        ? const [PromiseGoogleTaskList(id: '@default', title: '기본 목록')]
        : tasklists;
    return showModalBottomSheet<PromiseGoogleTaskList>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.all(AppSpacing.md),
          children: [
            const ListTile(
              leading: Icon(Icons.task_alt_outlined),
              title: Text('Google Tasks 목록 선택'),
            ),
            for (final tasklist in options)
              ListTile(
                title: Text(tasklist.title),
                subtitle: Text(tasklist.id),
                onTap: () => Navigator.of(sheetContext).pop(tasklist),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _syncGoogleTask(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    PromiseLedgerEntry entry,
  ) async {
    try {
      final accessToken = await _requestGoogleTasksAccessToken(context);
      if (accessToken == null) return;
      final metadata = _googleTaskMetadata(entry);
      final synced = await ref.read(promiseRadarApiProvider).syncExternalTask(
            entry.id,
            PromiseExternalTaskSyncRequest(
              accessToken: accessToken,
              tasklist: metadata['tasklist'] ?? '@default',
              externalId: metadata['external_id'],
            ),
          );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseRadarDashboardProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(synced.message)),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Google Tasks 동기화에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _updateGoogleTaskFromLedger(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    PromiseLedgerEntry entry,
  ) async {
    try {
      final accessToken = await _requestGoogleTasksAccessToken(context);
      if (accessToken == null) return;
      final metadata = _googleTaskMetadata(entry);
      final updated = await ref
          .read(promiseRadarApiProvider)
          .updateExternalTask(
            entry.id,
            PromiseExternalTaskUpdateRequest(
              accessToken: accessToken,
              tasklist: metadata['tasklist'] ?? '@default',
              externalId: metadata['external_id'],
              status: entry.status == 'completed' ? 'completed' : 'needsAction',
              title: entry.text,
            ),
          );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseRadarDashboardProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(updated.message)),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Google Tasks 업데이트에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _createReminderCandidate(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    String entryId,
  ) async {
    try {
      await ref.read(promiseRadarApiProvider).createCalendarCandidate(entryId);
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseNextMeetingBriefingProvider);
      ref.invalidate(promiseRadarDashboardProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 알림 후보가 생성됐습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 알림 생성에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _showAccuracyReportSheet(
    BuildContext context,
    WidgetRef ref,
  ) async {
    try {
      final report =
          await ref.read(promiseRadarApiProvider).getAccuracyReport();
      if (!context.mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (sheetContext) => SafeArea(
          child: FractionallySizedBox(
            heightFactor: 0.8,
            child: ListView(
              padding: const EdgeInsets.all(AppSpacing.md),
              children: [
                ListTile(
                  leading: Icon(
                    report.belowTarget
                        ? Icons.warning_amber_outlined
                        : Icons.analytics_outlined,
                  ),
                  title: const Text('Promise Radar 정확도'),
                  subtitle: Text(
                    '정확도 ${(report.evaluation.accuracy * 100).round()}% · 실제 회의 label ${report.realMeetingCaseCount}/${report.targetCaseCount}',
                  ),
                ),
                Wrap(
                  spacing: AppSpacing.xs,
                  runSpacing: AppSpacing.xs,
                  children: [
                    _PromiseMetricPill(
                      label: '정답',
                      value:
                          '${report.evaluation.correctCount}/${report.evaluation.caseCount}',
                    ),
                    if (report.coverage['real_meeting_target'] != null)
                      _PromiseMetricPill(
                        label: '실제 label',
                        value: _percentageLabel(
                            report.coverage['real_meeting_target']!),
                      ),
                    if (report.coverage['manifest_case_match'] != null)
                      _PromiseMetricPill(
                        label: 'manifest',
                        value: _percentageLabel(
                            report.coverage['manifest_case_match']!),
                      ),
                    if (report.qualityWarnings.isNotEmpty)
                      _PromiseMetricPill(
                        label: 'warning',
                        value: '${report.qualityWarnings.length}',
                      ),
                  ],
                ),
                ListTile(
                  title: const Text('Fixture'),
                  subtitle: Text(report.fixturePath),
                ),
                if (report.qualityWarnings.isNotEmpty) ...[
                  const Divider(),
                  for (final warning in report.qualityWarnings.take(5))
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.warning_amber_outlined),
                      title: Text(warning),
                    ),
                ],
                if (report.evaluation.confidenceBuckets.isNotEmpty) ...[
                  const Divider(),
                  ListTile(
                    dense: true,
                    title: const Text('Confidence bucket'),
                    subtitle: Text(
                      report.evaluation.confidenceBuckets.entries.map((entry) {
                        final value = entry.value;
                        final total = value['case_count'] as int? ?? 0;
                        final accuracy =
                            (value['accuracy'] as num?)?.toDouble() ?? 0;
                        return '${entry.key}: ${_percentageLabel(accuracy)} ($total)';
                      }).join(' · '),
                    ),
                  ),
                ],
                if (report.coverage.isNotEmpty) ...[
                  const Divider(),
                  for (final entry in report.coverage.entries)
                    ListTile(
                      dense: true,
                      title: Text(entry.key),
                      trailing: Text(_percentageLabel(entry.value)),
                    ),
                ],
                const Divider(),
                for (final entry in report.statusCounts.entries)
                  ListTile(
                    dense: true,
                    title: Text(_statusLabel(entry.key)),
                    trailing: Text('${entry.value}건'),
                  ),
                const Divider(),
                for (final entry in report.sourceCounts.entries)
                  ListTile(
                    dense: true,
                    title: Text(entry.key),
                    trailing: Text(
                      report.sourceQuality[entry.key]?['golden_case_count'] !=
                              null
                          ? '${entry.value}건 / golden ${report.sourceQuality[entry.key]?['golden_case_count']}'
                          : '${entry.value}건',
                    ),
                  ),
                if (report.evaluation.failures.isNotEmpty) ...[
                  const Divider(),
                  for (final failure in report.evaluation.failures.take(5))
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.error_outline),
                      title: Text(failure['id']?.toString() ?? 'unknown'),
                      subtitle: Text(failure.toString()),
                    ),
                ],
              ],
            ),
          ),
        ),
      );
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Promise Radar 정확도 보고서를 불러오지 못했습니다.')),
        );
      }
    }
  }

  Future<void> _showAutomationPolicySheet(
    BuildContext context,
    WidgetRef ref,
  ) async {
    try {
      final policy =
          await ref.read(promiseRadarApiProvider).getAutomationPolicy();
      if (!context.mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        builder: (sheetContext) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              ListTile(
                leading: const Icon(Icons.rule_folder_outlined),
                title: const Text('자동화 정책'),
                subtitle: Text(_automationPolicyLabel(policy.mode)),
              ),
              for (final option in const [
                'safe_auto',
                'preview_only',
                'completed_only',
                'manual_only',
              ])
                ListTile(
                  leading: Icon(
                    policy.mode == option
                        ? Icons.check_circle
                        : Icons.radio_button_unchecked,
                  ),
                  title: Text(_automationPolicyLabel(option)),
                  onTap: () => _updateAutomationPolicy(
                    sheetContext,
                    ref,
                    option,
                  ),
                ),
            ],
          ),
        ),
      );
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('자동화 정책을 불러오지 못했습니다.')),
        );
      }
    }
  }

  Future<void> _updateAutomationPolicy(
    BuildContext context,
    WidgetRef ref,
    String mode,
  ) async {
    final statuses = mode == 'completed_only'
        ? const ['completed']
        : mode == 'manual_only' || mode == 'preview_only'
            ? const <String>[]
            : const ['changed', 'completed', 'delayed', 'dismissed'];
    try {
      await ref.read(promiseRadarApiProvider).updateAutomationPolicy(
            PromiseAutomationPolicyUpdateRequest(
              mode: mode,
              allowedAutoStatuses: statuses,
              highRiskRequiresReview: true,
              assigneeChangeRequiresReview: true,
              conflictRequiresReview: true,
            ),
          );
      ref.invalidate(promiseLearningProfileProvider);
      if (context.mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('자동화 정책을 저장했습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('자동화 정책 저장에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _showDigestPreferenceSheet(
    BuildContext context,
    WidgetRef ref,
  ) async {
    try {
      final preference =
          await ref.read(promiseRadarApiProvider).getDigestPreference();
      if (!context.mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        builder: (sheetContext) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              ListTile(
                leading: const Icon(Icons.notifications_outlined),
                title: const Text('Digest Push'),
                subtitle: Text(
                  preference.enabled
                      ? '${_digestCadenceLabel(preference.cadence)} · ${preference.localTime}'
                      : '예약 발송 꺼짐',
                ),
                trailing: Switch(
                  value: preference.enabled,
                  onChanged: (enabled) => _updateDigestPreference(
                    sheetContext,
                    ref,
                    preference,
                    enabled: enabled,
                  ),
                ),
              ),
              for (final cadence in const ['daily', 'weekly'])
                ListTile(
                  leading: Icon(
                    preference.cadence == cadence
                        ? Icons.check_circle
                        : Icons.radio_button_unchecked,
                  ),
                  title: Text(_digestCadenceLabel(cadence)),
                  subtitle: Text(
                    cadence == 'daily' ? '매일 아침 확인할 약속' : '이번 주 확인할 약속',
                  ),
                  onTap: () => _updateDigestPreference(
                    sheetContext,
                    ref,
                    preference,
                    cadence: cadence,
                    enabled: true,
                  ),
                ),
              const ListTile(
                dense: true,
                leading: Icon(Icons.schedule_outlined),
                title: Text('기본 발송 시각'),
                subtitle: Text('08:30 Asia/Seoul · 조용한 시간 22:00-07:00'),
              ),
            ],
          ),
        ),
      );
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Digest 설정을 불러오지 못했습니다.')),
        );
      }
    }
  }

  Future<void> _updateDigestPreference(
    BuildContext context,
    WidgetRef ref,
    PromiseDigestPreference preference, {
    bool? enabled,
    String? cadence,
  }) async {
    try {
      await ref.read(promiseRadarApiProvider).updateDigestPreference(
            PromiseDigestPreferenceUpdateRequest(
              enabled: enabled ?? preference.enabled,
              cadence: cadence ?? preference.cadence,
              localTime: preference.localTime,
              timezone: preference.timezone,
              quietHoursStart: preference.quietHoursStart,
              quietHoursEnd: preference.quietHoursEnd,
            ),
          );
      if (context.mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Digest 설정을 저장했습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Digest 설정 저장에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _dispatchPreMeetingBrief(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
  ) async {
    try {
      final response = await ref
          .read(promiseRadarApiProvider)
          .dispatchPreMeetingBriefNotifications();
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '회의 전 브리프 발송 ${response.sentCount}건 · 검토 ${response.consideredCount}건 · 실패 ${response.failureCount}건',
            ),
          ),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('회의 전 브리프 푸시 발송에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _runAutopilot(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
  ) async {
    try {
      final queue = await ref
          .read(promiseRadarApiProvider)
          .getAutopilotReviewQueue(summaryTaskId);
      if (context.mounted) {
        await _showAutopilotReviewQueueSheet(
          context,
          ref,
          summaryTaskId,
          queue,
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 자동 판정 대기열 조회에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _showAutopilotReviewQueueSheet(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    PromiseAutopilotReviewQueue queue,
  ) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) {
        var filter = 'all';
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final filtered = queue.items.where((item) {
              final assessment = item.assessment;
              return switch (filter) {
                'conflict' => assessment.conflictDetected,
                'weak' => !assessment.evidenceLocked ||
                    assessment.confidence < assessment.threshold,
                'high_risk' => item.ledgerEntry.riskLevel == 'high',
                'due' => item.ledgerEntry.dueAt != null ||
                    item.ledgerEntry.dueDate != null,
                _ => true,
              };
            }).toList();
            final actionableFiltered = filtered
                .where((item) =>
                    !item.assessment.conflictDetected &&
                    item.assessment.suggestedStatus !=
                        item.assessment.previousStatus)
                .toList();
            return SafeArea(
              child: FractionallySizedBox(
                heightFactor: 0.9,
                child: ListView(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  children: [
                    ListTile(
                      leading: const Icon(Icons.fact_check_outlined),
                      title: const Text('확정 대기 약속함'),
                      subtitle: Text(
                        '${filtered.length}/${queue.queueCount}개 표시 · ${queue.actionableCount}개 확정 가능 · 충돌 ${queue.conflictCount}개',
                      ),
                      trailing: actionableFiltered.isEmpty
                          ? null
                          : TextButton(
                              onPressed: () => _confirmAllAutopilotAssessments(
                                sheetContext,
                                ref,
                                summaryTaskId,
                                actionableFiltered,
                              ),
                              child: const Text('현재 모두 맞음'),
                            ),
                    ),
                    Wrap(
                      spacing: AppSpacing.xs,
                      runSpacing: AppSpacing.xs,
                      children: [
                        for (final option in const [
                          ('all', '전체'),
                          ('conflict', '충돌'),
                          ('weak', '약한 근거'),
                          ('high_risk', '고위험'),
                          ('due', '기한 있음'),
                        ])
                          FilterChip(
                            label: Text(option.$2),
                            selected: filter == option.$1,
                            onSelected: (_) =>
                                setSheetState(() => filter = option.$1),
                          ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    if (filtered.isNotEmpty)
                      _buildAutopilotQueueSummary(
                        context,
                        filtered,
                        actionableFiltered,
                      ),
                    if (filtered.isEmpty)
                      const ListTile(title: Text('확인할 약속 후보가 없습니다.')),
                    for (final item in filtered)
                      _buildAutopilotReviewTile(
                        context,
                        sheetContext,
                        ref,
                        summaryTaskId,
                        item,
                      ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildAutopilotQueueSummary(
    BuildContext context,
    List<PromiseAutopilotReviewItem> filtered,
    List<PromiseAutopilotReviewItem> actionable,
  ) {
    final theme = Theme.of(context);
    final statusCounts = <String, int>{};
    for (final item in actionable) {
      statusCounts.update(
        item.assessment.suggestedStatus,
        (value) => value + 1,
        ifAbsent: () => 1,
      );
    }
    final weakCount = filtered
        .where((item) =>
            !item.assessment.evidenceLocked ||
            item.assessment.confidence < item.assessment.threshold)
        .length;
    final lockedCount =
        filtered.where((item) => item.assessment.evidenceLocked).length;
    final highRiskCount =
        filtered.where((item) => item.ledgerEntry.riskLevel == 'high').length;
    final dueCount = filtered
        .where((item) =>
            item.ledgerEntry.dueAt != null || item.ledgerEntry.dueDate != null)
        .length;
    final statusSummary = statusCounts.entries
        .map((entry) => '${_statusLabel(entry.key)} ${entry.value}')
        .join(' · ');

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.sm),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '일괄 확정 diff preview',
              style: theme.textTheme.labelLarge,
            ),
            const SizedBox(height: AppSpacing.xs),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                _PromiseMetricPill(label: '표시', value: '${filtered.length}'),
                _PromiseMetricPill(
                    label: '확정 가능', value: '${actionable.length}'),
                _PromiseMetricPill(label: '근거 잠김', value: '$lockedCount'),
                _PromiseMetricPill(label: '약한 근거', value: '$weakCount'),
                _PromiseMetricPill(label: '고위험', value: '$highRiskCount'),
                _PromiseMetricPill(label: '기한', value: '$dueCount'),
              ],
            ),
            if (statusSummary.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                '상태 변경: $statusSummary',
                style: theme.textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildAutopilotReviewTile(
    BuildContext parentContext,
    BuildContext sheetContext,
    WidgetRef ref,
    String summaryTaskId,
    PromiseAutopilotReviewItem item,
  ) {
    final assessment = item.assessment;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.sm),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                assessment.conflictDetected
                    ? Icons.report_problem_outlined
                    : Icons.auto_fix_high_outlined,
              ),
              title: Text(item.ledgerEntry.text),
              subtitle: Text(
                [
                  '${_statusLabel(assessment.previousStatus)} → ${_statusLabel(assessment.suggestedStatus)}',
                  '${(assessment.confidence * 100).round()}%',
                  if (assessment.evidenceLocked) '근거 잠김',
                  if (assessment.conflictDetected) '충돌 감지',
                ].join(' · '),
              ),
            ),
            Text(
              assessment.conflictReason ?? assessment.reason,
              style: Theme.of(parentContext).textTheme.bodySmall,
            ),
            const SizedBox(height: AppSpacing.xs),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                _PromiseMetricPill(
                  label: 'threshold',
                  value: _percentageLabel(assessment.threshold),
                ),
                _PromiseMetricPill(
                  label: 'similarity',
                  value: _percentageLabel(assessment.explanation.similarity),
                ),
                _PromiseMetricPill(
                  label: 'factors',
                  value: '${assessment.explanation.confidenceFactors.length}',
                ),
                _PromiseMetricPill(
                  label: 'markers',
                  value: '${assessment.evidencePack?.markerHits.length ?? 0}',
                ),
              ],
            ),
            if (assessment.conflictDetected) ...[
              const SizedBox(height: AppSpacing.sm),
              _buildConflictSignalPanel(parentContext, assessment),
            ],
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                OutlinedButton.icon(
                  onPressed: () => _showEvidencePackViewer(
                    parentContext,
                    assessment,
                  ),
                  icon: const Icon(Icons.travel_explore_outlined, size: 18),
                  label: const Text('근거'),
                ),
                if (!assessment.conflictDetected &&
                    assessment.suggestedStatus != assessment.previousStatus)
                  FilledButton(
                    onPressed: () => _confirmAutopilotAssessment(
                      sheetContext,
                      ref,
                      summaryTaskId,
                      assessment,
                    ),
                    child: const Text('맞음'),
                  ),
                if (!assessment.conflictDetected &&
                    assessment.suggestedStatus != assessment.previousStatus)
                  TextButton(
                    onPressed: () => _rejectAutopilotAssessment(
                      sheetContext,
                      ref,
                      summaryTaskId,
                      assessment,
                    ),
                    child: const Text('거절'),
                  ),
                if (assessment.conflictDetected)
                  for (final status in const [
                    'completed',
                    'delayed',
                    'changed',
                    'dismissed',
                  ])
                    TextButton(
                      onPressed: () => _resolveAutopilotConflict(
                        sheetContext,
                        ref,
                        summaryTaskId,
                        assessment.ledgerEntryId,
                        status,
                      ),
                      child: Text(_statusLabel(status)),
                    ),
                if (assessment.conflictDetected)
                  TextButton.icon(
                    onPressed: () {
                      Navigator.of(sheetContext).pop();
                      _showSplitLedgerDialog(
                        parentContext,
                        ref,
                        summaryTaskId,
                        item.ledgerEntry,
                      );
                    },
                    icon: const Icon(Icons.call_split_outlined, size: 18),
                    label: const Text('분리 추천'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConflictSignalPanel(
    BuildContext context,
    PromiseAutopilotAssessment assessment,
  ) {
    final markers = assessment.evidencePack?.markerHits ?? const <String>[];
    final positive = markers
        .where(
          (marker) =>
              marker.contains('완료') ||
              marker.contains('done') ||
              marker.contains('completed'),
        )
        .toList();
    final blocking = markers
        .where(
          (marker) =>
              marker.contains('아직') ||
              marker.contains('지연') ||
              marker.contains('못') ||
              marker.contains('delayed') ||
              marker.contains('blocked') ||
              marker.contains('cancel'),
        )
        .toList();
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.sm),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '충돌 근거 비교',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
                '완료 신호: ${positive.isEmpty ? assessment.suggestedStatus : positive.join(', ')}'),
            Text(
                '지연/제외 신호: ${blocking.isEmpty ? assessment.conflictReason ?? '추가 확인 필요' : blocking.join(', ')}'),
            const SizedBox(height: AppSpacing.xs),
            Text(
              '한 발화에 상반된 신호가 있으면 자동 적용하지 않고 분리 후보로 검토합니다.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmAutopilotAssessment(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    PromiseAutopilotAssessment assessment, {
    bool closeSheet = true,
  }) async {
    try {
      await ref.read(promiseRadarApiProvider).confirmAutopilotAssessment(
            assessment.ledgerEntryId,
            taskId: summaryTaskId,
            suggestedStatus: assessment.suggestedStatus,
            note: '사용자가 Autopilot 미리보기를 확인했습니다.',
          );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseNextMeetingBriefingProvider);
      ref.invalidate(promiseRadarDashboardProvider);
      ref.invalidate(promiseLearningProfileProvider);
      if (context.mounted) {
        if (closeSheet) {
          Navigator.of(context).pop();
        }
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('자동 판정을 확정했습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('자동 판정 확정에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _confirmAllAutopilotAssessments(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    List<PromiseAutopilotReviewItem> items,
  ) async {
    final targets = items
        .map((item) => item.assessment)
        .where(
          (assessment) =>
              !assessment.conflictDetected &&
              assessment.suggestedStatus != assessment.previousStatus,
        )
        .toList();
    var confirmed = 0;
    for (final assessment in targets) {
      try {
        await ref.read(promiseRadarApiProvider).confirmAutopilotAssessment(
              assessment.ledgerEntryId,
              taskId: summaryTaskId,
              suggestedStatus: assessment.suggestedStatus,
              note: '사용자가 Autopilot review queue에서 일괄 확인했습니다.',
            );
        confirmed += 1;
      } catch (_) {
        // 개별 후보 실패는 나머지 확정을 계속 진행합니다.
      }
    }
    ref.invalidate(promiseRadarProvider(summaryTaskId));
    ref.invalidate(promiseLedgerProvider);
    ref.invalidate(promiseNextMeetingBriefingProvider);
    ref.invalidate(promiseRadarDashboardProvider);
    ref.invalidate(promiseLearningProfileProvider);
    if (context.mounted) {
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('자동 판정 $confirmed개를 확정했습니다.')),
      );
    }
  }

  Future<void> _rejectAutopilotAssessment(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    PromiseAutopilotAssessment assessment,
  ) async {
    try {
      await ref.read(promiseRadarApiProvider).rejectAutopilotReviewItem(
            assessment.ledgerEntryId,
            taskId: summaryTaskId,
            suggestedStatus: assessment.suggestedStatus,
            note: 'Review Queue에서 자동 판정을 거절했습니다.',
          );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseLearningProfileProvider);
      if (context.mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('거절 이력을 저장하고 queue에서 제외했습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('자동 판정 거절 처리에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _resolveAutopilotConflict(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    String entryId,
    String status,
  ) async {
    try {
      await ref.read(promiseRadarApiProvider).resolveAutopilotConflict(
            entryId,
            PromiseConflictResolveRequest(
              status: status,
              note: 'Review Queue에서 충돌 판정을 해결했습니다.',
            ),
          );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseNextMeetingBriefingProvider);
      ref.invalidate(promiseRadarDashboardProvider);
      if (context.mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('충돌 판정을 해결했습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('충돌 판정 해결에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _showEvidencePackViewer(
    BuildContext context,
    PromiseAutopilotAssessment assessment,
  ) async {
    await _showEvidencePackSheet(
      context,
      pack: assessment.evidencePack,
      explanation: assessment.explanation,
    );
  }

  Future<void> _showLatestEvidencePack(
    BuildContext context,
    WidgetRef ref,
    String entryId,
  ) async {
    try {
      final pack = await ref
          .read(promiseRadarApiProvider)
          .getLatestEvidencePack(entryId);
      if (!context.mounted) return;
      await _showEvidencePackSheet(context, pack: pack);
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('저장된 Evidence Pack을 찾지 못했습니다.')),
        );
      }
    }
  }

  Future<void> _showEvidenceComparison(
    BuildContext context,
    WidgetRef ref,
    String entryId,
  ) async {
    try {
      final comparison = await ref
          .read(promiseRadarApiProvider)
          .getEvidenceComparison(entryId);
      if (!context.mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (sheetContext) => SafeArea(
          child: FractionallySizedBox(
            heightFactor: 0.82,
            child: ListView(
              padding: const EdgeInsets.all(AppSpacing.md),
              children: [
                ListTile(
                  leading: const Icon(Icons.compare_arrows_outlined),
                  title: const Text('근거 비교'),
                  subtitle: Text(comparison.summary),
                ),
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.xs,
                  children: [
                    _PromiseMetricPill(
                      label: '기존',
                      value:
                          '${((comparison.previousSimilarity ?? 0) * 100).round()}%',
                    ),
                    _PromiseMetricPill(
                      label: '현재',
                      value:
                          '${((comparison.currentSimilarity ?? 0) * 100).round()}%',
                    ),
                    if (comparison.similarityDelta != null)
                      _PromiseMetricPill(
                        label: '변화',
                        value:
                            '${(comparison.similarityDelta! * 100).round()}%',
                      ),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                ListTile(
                  title: const Text('기존 원장 근거'),
                  subtitle: Text(comparison.previousText ?? '근거 없음'),
                ),
                ListTile(
                  title: const Text('최신 자동 판정 근거'),
                  subtitle: Text(comparison.currentText ?? 'Evidence Pack 없음'),
                ),
                if (comparison.sharedTerms.isNotEmpty)
                  ListTile(
                    title: const Text('공유 핵심어'),
                    subtitle: Text(comparison.sharedTerms.join(', ')),
                  ),
                if (comparison.currentPack?.markerHits.isNotEmpty == true)
                  ListTile(
                    title: const Text('Marker Hit'),
                    subtitle:
                        Text(comparison.currentPack!.markerHits.join(', ')),
                  ),
                for (final evidence in comparison.previousEvidence)
                  ListTile(
                    dense: true,
                    leading: const Icon(Icons.notes_outlined),
                    title: Text(_evidenceLabel(evidence)),
                    subtitle: Text(evidence.transcript),
                  ),
              ],
            ),
          ),
        ),
      );
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 근거 비교를 불러오지 못했습니다.')),
        );
      }
    }
  }

  Future<void> _showEvidencePackSheet(
    BuildContext context, {
    PromiseEvidencePack? pack,
    PromiseMatchExplanation? explanation,
  }) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => SafeArea(
        child: FractionallySizedBox(
          heightFactor: 0.8,
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              ListTile(
                leading: const Icon(Icons.travel_explore_outlined),
                title: const Text('Evidence Pack'),
                subtitle: Text(
                  '유사도 ${((pack?.similarity ?? explanation?.similarity ?? 0) * 100).round()}%',
                ),
              ),
              ListTile(
                dense: true,
                leading: const Icon(Icons.inventory_2_outlined),
                title: const Text('감사 요약'),
                subtitle: Text(_evidencePackAuditSummary(pack, explanation)),
              ),
              ListTile(
                title: const Text('매칭 발화'),
                subtitle: Text(
                  pack?.matchedText ?? explanation?.matchedText ?? '연결된 발화 없음',
                ),
              ),
              if (pack != null && pack.markerHits.isNotEmpty)
                ListTile(
                  title: const Text('Marker Hit'),
                  subtitle: Text(pack.markerHits.join(', ')),
                ),
              for (final factor in pack?.confidenceFactors ??
                  explanation?.confidenceFactors ??
                  const <String>[])
                ListTile(
                  dense: true,
                  leading: const Icon(Icons.check_circle_outline),
                  title: Text(factor),
                ),
              for (final evidence in pack?.evidence ??
                  explanation?.evidence ??
                  const <PromiseRadarEvidence>[])
                ListTile(
                  dense: true,
                  leading: const Icon(Icons.notes_outlined),
                  title: Text(_evidenceLabel(evidence)),
                  subtitle: Text(evidence.transcript),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _showMatchExplanation(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    String entryId,
  ) async {
    try {
      final explanation = await ref
          .read(promiseRadarApiProvider)
          .explainLedgerEntry(entryId, taskId: summaryTaskId);
      if (!context.mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        builder: (sheetContext) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              ListTile(
                leading: const Icon(Icons.psychology_alt_outlined),
                title: const Text('약속 판정 근거'),
                subtitle: Text(
                  '유사도 ${(explanation.similarity * 100).round()}%',
                ),
              ),
              ListTile(
                title: Text(explanation.rationale),
                subtitle: Text(explanation.matchedText ?? '연결된 발화 없음'),
              ),
              if (explanation.overlapTerms.isNotEmpty)
                ListTile(
                  title: const Text('겹친 핵심어'),
                  subtitle: Text(explanation.overlapTerms.join(', ')),
                ),
              for (final factor in explanation.confidenceFactors)
                ListTile(
                  dense: true,
                  leading: const Icon(Icons.check_circle_outline),
                  title: Text(factor),
                ),
            ],
          ),
        ),
      );
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 근거 설명을 불러오지 못했습니다.')),
        );
      }
    }
  }

  Future<void> _exportCalendarEvent(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    String entryId,
  ) async {
    try {
      final exported =
          await ref.read(promiseRadarApiProvider).exportCalendarEvent(entryId);
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      final uri = Uri.tryParse(exported.googleCalendarUrl);
      final opened = uri != null &&
          await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!opened) {
        await Clipboard.setData(ClipboardData(text: exported.icsContent));
      }
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              opened ? 'Google Calendar를 열었습니다.' : 'ICS 내용을 복사했습니다.',
            ),
          ),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('캘린더 내보내기에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _showAssigneeSuggestions(
    BuildContext context,
    WidgetRef ref,
    String entryId,
  ) async {
    try {
      final suggestions =
          await ref.read(promiseRadarApiProvider).suggestAssignees(entryId);
      if (!context.mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        builder: (sheetContext) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              ListTile(
                leading: const Icon(Icons.person_search_outlined),
                title: const Text('담당자 추천'),
                subtitle: Text('${suggestions.length}명 후보'),
              ),
              if (suggestions.isEmpty)
                const ListTile(title: Text('추천할 팀 사용자가 없습니다.')),
              for (final suggestion in suggestions)
                ListTile(
                  title: Text(suggestion.displayName),
                  subtitle: Text(suggestion.rationale),
                  trailing: Text('${(suggestion.confidence * 100).round()}%'),
                ),
            ],
          ),
        ),
      );
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('담당자 추천을 불러오지 못했습니다.')),
        );
      }
    }
  }

  Future<void> _updateLedgerStatus(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    String entryId,
    String status, {
    bool? userConfirmed,
  }) async {
    try {
      await ref.read(promiseRadarApiProvider).updateLedgerEntry(
            entryId,
            PromiseLedgerUpdateRequest(
              status: status,
              userConfirmed: userConfirmed,
            ),
          );
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseNextMeetingBriefingProvider);
      ref.invalidate(promiseRadarDashboardProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 원장이 업데이트됐습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속 원장 업데이트에 실패했습니다.')),
        );
      }
    }
  }

  Future<void> _createActionItem(
    BuildContext context,
    WidgetRef ref,
    String summaryTaskId,
    String entryId,
  ) async {
    try {
      await ref.read(promiseRadarApiProvider).createActionItem(entryId);
      ref.invalidate(promiseRadarProvider(summaryTaskId));
      ref.invalidate(promiseLedgerProvider);
      ref.invalidate(promiseRadarDashboardProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('약속이 할 일로 연결됐습니다.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('할 일 생성에 실패했습니다.')),
        );
      }
    }
  }
}

class _PromiseMetricPill extends StatelessWidget {
  final String label;
  final String value;

  const _PromiseMetricPill({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '$label $value',
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  final String status;

  const _StatusChip({required this.status});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final label = switch (status) {
      'completed' => '완료',
      'dismissed' => '제외',
      'delegated' => '위임',
      'blocked' => '차단',
      'delayed' => '지연',
      'changed' => '변경',
      _ => '진행',
    };
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _RiskChip extends StatelessWidget {
  final String level;

  const _RiskChip({required this.level});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (label, color) = switch (level) {
      'critical' => ('긴급', theme.colorScheme.error),
      'high' => ('높음', theme.colorScheme.error),
      'medium' => ('중간', AppColors.warning),
      _ => ('낮음', AppColors.success),
    };
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: 4,
      ),
      decoration: BoxDecoration(
        color: color.withAlpha(28),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: theme.textTheme.labelSmall?.copyWith(
          color: color,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _PromiseTile extends StatelessWidget {
  final PromiseRadarPromise item;

  const _PromiseTile({required this.item});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final meta = [
      if (item.owner?.trim().isNotEmpty == true) item.owner!,
      if (item.dueDate?.trim().isNotEmpty == true) item.dueDate!,
      item.priority,
    ].join(' · ');

    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            item.text,
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          if (meta.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(
              meta,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// 우선순위 배지 색상 상수 (SPEC-APP-003 REQ-APP-033)
const _priorityColors = {
  'high': AppColors.error,
  'medium': AppColors.warning,
  'low': AppColors.success,
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
            _priorityColors[item.priority] ?? AppColors.warning;

        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: CheckboxListTile(
            value: done,
            // 작업 내용 (완료 시 취소선)
            title: Text(
              item.task,
              style: TextStyle(
                decoration: done ? TextDecoration.lineThrough : null,
                color: done ? Theme.of(context).colorScheme.outline : null,
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
