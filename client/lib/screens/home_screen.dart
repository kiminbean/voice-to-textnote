// 홈 화면 - 미팅 목록 표시 (모던 미니멀)
// @MX:NOTE: SPEC-TMPL/SEARCH/TEAM/HISTSYNC/GUEST 통합 진입점
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/providers/theme_mode_provider.dart';
import 'package:voice_to_textnote/services/history_api.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';
import 'package:voice_to_textnote/widgets/meeting_card.dart';
import 'package:voice_to_textnote/widgets/offline_banner.dart';
import 'package:voice_to_textnote/widgets/shimmer_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meetingsAsync = ref.watch(meetingListProvider);
    final authState = ref.watch(authStateProvider);

    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () => _onRefresh(context, ref),
        child: CustomScrollView(
          slivers: [
            // 헤더
            SliverAppBar.large(
              title: _buildHeader(context, authState.isGuest),
              actions: [_buildMenuButton(context, ref)],
              pinned: false,
            ),
            // 오프라인 배너
            if (authState.isGuest)
              SliverToBoxAdapter(child: _buildGuestBanner(context, ref)),
            const SliverToBoxAdapter(child: OfflineBanner()),
            SliverToBoxAdapter(child: _buildOwllHero(context)),
            SliverToBoxAdapter(child: _buildCaptureShortcuts(context, ref)),
            // 본문
            meetingsAsync.when(
              loading: () => SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                sliver: SliverList.builder(
                    itemCount: 3, itemBuilder: (_, __) => const ShimmerCard()),
              ),
              error: (_, __) => const SliverFillRemaining(
                child: EmptyStateWidget(
                  icon: Icons.cloud_off_rounded,
                  title: '미팅 목록을 불러올 수 없습니다',
                  subtitle: '잠시 후 다시 시도해주세요',
                ),
              ),
              data: (meetings) => meetings.isEmpty
                  ? SliverFillRemaining(
                      hasScrollBody: false,
                      child: EmptyStateWidget(
                        icon: Icons.graphic_eq_rounded,
                        title: '아직 녹음된 미팅이 없어요',
                        subtitle: '첫 번째 회의를 녹음해 보세요',
                        actionLabel: '녹음 시작하기',
                        onAction: () => context.push('/recording'),
                      ),
                    )
                  : SliverPadding(
                      padding: const EdgeInsets.fromLTRB(AppSpacing.lg,
                          AppSpacing.sm, AppSpacing.lg, AppSpacing.xxxl),
                      sliver: SliverList.builder(
                        itemCount: meetings.length,
                        itemBuilder: (context, index) {
                          final meeting = meetings[index];
                          return Padding(
                            padding:
                                const EdgeInsets.only(bottom: AppSpacing.sm),
                            child: MeetingCard(
                              meeting: meeting,
                              onTap: () => meeting.sourceUrl != null &&
                                      meeting.minutesTaskId == null
                                  ? _showOnlineMeetingDetail(
                                      context,
                                      meeting,
                                    )
                                  : context.push('/result/${meeting.id}'),
                              onLongPress: () =>
                                  _onLongPress(context, ref, meeting.id),
                            ),
                          );
                        },
                      ),
                    ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/recording'),
        icon: const Icon(Icons.mic_rounded),
        label: const Text('지금 녹음'),
      ),
    );
  }

  // 헤더 타이틀
  Widget _buildHeader(BuildContext context, bool isGuest) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'Owll Notes',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w700,
                letterSpacing: -0.3,
              ),
        ),
      ],
    );
  }

  Widget _buildOwllHero(BuildContext context) {
    final scheme = AppColors.of(context);
    return Container(
      margin: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.sm,
        AppSpacing.lg,
        AppSpacing.md,
      ),
      padding: const EdgeInsets.all(AppSpacing.xl),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF14203B),
            Color(0xFF06184A),
            Color(0xFF062F2C),
          ],
        ),
        borderRadius: AppRadius.brLg,
        boxShadow: AppElevation.floating(Colors.black),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: const BoxDecoration(
                  color: AppColors.info,
                  borderRadius: AppRadius.brMd,
                ),
                child:
                    const Icon(Icons.auto_awesome_rounded, color: Colors.white),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Text(
                  'AI가 회의 기록을 대신합니다',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            '녹음부터 실시간 전사, 요약, 액션 아이템, 팀 공유까지 한 흐름으로 정리하세요.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white.withAlpha(220),
                  height: 1.45,
                ),
          ),
          const SizedBox(height: AppSpacing.lg),
          const Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              _HeroBadge(icon: Icons.mic_rounded, label: '원탭 녹음'),
              _HeroBadge(icon: Icons.subject_rounded, label: '실시간 전사'),
              _HeroBadge(icon: Icons.checklist_rounded, label: '액션 아이템'),
              _HeroBadge(icon: Icons.ios_share_rounded, label: '공유/내보내기'),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          FilledButton.icon(
            onPressed: () => context.push('/recording'),
            icon: const Icon(Icons.radio_button_checked_rounded),
            label: const Text('Download Now 대신 바로 기록 시작'),
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFFF8DD3F),
              foregroundColor: const Color(0xFF102027),
              minimumSize: const Size.fromHeight(48),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            '#1 AI Note Taker 스타일 벤치마크',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: scheme.isDark
                      ? Colors.white.withAlpha(180)
                      : Colors.white.withAlpha(200),
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildCaptureShortcuts(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        0,
        AppSpacing.lg,
        AppSpacing.lg,
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _ShortcutTile(
                  icon: Icons.upload_file_rounded,
                  title: '파일 업로드',
                  subtitle: 'WAV/MP3/M4A/MP4/OGG',
                  onTap: () => context.push('/recording?mode=upload'),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: _ShortcutTile(
                  icon: Icons.video_call_rounded,
                  title: '온라인 회의',
                  subtitle: 'Zoom/Meet/Teams',
                  onTap: () => _showMeetingLinkSheet(context, ref),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          _ShortcutTile(
            icon: Icons.link_rounded,
            title: 'URL/Transcript',
            subtitle: 'YouTube, 웹 글, 외부 자료를 검색 가능한 회의록으로 가져오기',
            onTap: () => _showExternalTextImportSheet(context, ref),
          ),
        ],
      ),
    );
  }

  void _showExternalTextImportSheet(BuildContext context, WidgetRef ref) {
    var draftUrl = '';
    var draftTitle = '';
    var draftContent = '';
    var isSubmitting = false;
    String? errorText;

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
          left: AppSpacing.lg,
          right: AppSpacing.lg,
          top: AppSpacing.sm,
          bottom: MediaQuery.of(ctx).viewInsets.bottom + AppSpacing.xl,
        ),
        child: StatefulBuilder(
          builder: (ctx, setSheetState) {
            Future<void> submit() async {
              final url = draftUrl.trim();
              final title = draftTitle.trim();
              final content = draftContent.trim();
              final validationError =
                  _validateExternalImport(url, title, content);
              if (validationError != null) {
                setSheetState(() => errorText = validationError);
                return;
              }

              setSheetState(() {
                isSubmitting = true;
                errorText = null;
              });

              try {
                final result =
                    await ref.read(minutesApiProvider).importExternalText(
                          sourceUrl: url,
                          title: title,
                          content: content,
                          sourceType: _externalSourceType(url),
                        );
                final taskId = result['task_id'] as String;
                final meeting = Meeting(
                  id: taskId,
                  title: title,
                  createdAt: DateTime.now(),
                  status: MeetingStatus.completed,
                  sourceUrl: url,
                  minutesTaskId: taskId,
                );
                await ref
                    .read(meetingListProvider.notifier)
                    .addMeeting(meeting);

                if (!context.mounted) return;
                Navigator.of(ctx).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('$title을 가져왔습니다.')),
                );
              } catch (_) {
                if (!ctx.mounted) return;
                setSheetState(() {
                  isSubmitting = false;
                  errorText = '외부 자료를 가져올 수 없습니다. 잠시 후 다시 시도해주세요.';
                });
              }
            }

            return SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'URL/Transcript 가져오기',
                    style: Theme.of(ctx).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    '직접 보유한 transcript나 원문을 붙여넣으면 검색, 요약, 번역이 가능한 회의록으로 저장됩니다.',
                    style: Theme.of(ctx).textTheme.bodySmall,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    decoration: InputDecoration(
                      prefixIcon: const Icon(Icons.link_rounded),
                      labelText: '원본 URL',
                      errorText: errorText,
                    ),
                    keyboardType: TextInputType.url,
                    textInputAction: TextInputAction.next,
                    onChanged: (value) {
                      draftUrl = value;
                      if (errorText != null) {
                        setSheetState(() => errorText = null);
                      }
                    },
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    decoration: const InputDecoration(
                      prefixIcon: Icon(Icons.title_rounded),
                      labelText: '제목',
                    ),
                    textInputAction: TextInputAction.next,
                    onChanged: (value) => draftTitle = value,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    decoration: const InputDecoration(
                      alignLabelWithHint: true,
                      prefixIcon: Icon(Icons.notes_rounded),
                      labelText: 'Transcript 또는 원문',
                    ),
                    minLines: 5,
                    maxLines: 10,
                    keyboardType: TextInputType.multiline,
                    onChanged: (value) => draftContent = value,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  FilledButton.icon(
                    onPressed: isSubmitting ? null : submit,
                    icon: isSubmitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.library_add_check_rounded),
                    label: Text(isSubmitting ? '가져오는 중' : '검색 가능한 회의록으로 가져오기'),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  String? _validateExternalImport(String url, String title, String content) {
    if (url.isEmpty) return '원본 URL을 입력해주세요';
    final uri = Uri.tryParse(url);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
      return '올바른 URL을 입력해주세요';
    }
    if (title.isEmpty) return '제목을 입력해주세요';
    if (content.length < 20) return '본문은 20자 이상 입력해주세요';
    return null;
  }

  String _externalSourceType(String url) {
    final host = Uri.tryParse(url)?.host.toLowerCase() ?? '';
    if (host.contains('youtube.com') || host.contains('youtu.be')) {
      return 'youtube';
    }
    return 'web';
  }

  void _showMeetingLinkSheet(BuildContext context, WidgetRef ref) {
    var draftUrl = '';
    String? errorText;
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
          left: AppSpacing.lg,
          right: AppSpacing.lg,
          top: AppSpacing.sm,
          bottom: MediaQuery.of(ctx).viewInsets.bottom + AppSpacing.xl,
        ),
        child: StatefulBuilder(
          builder: (ctx, setSheetState) {
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('회의 링크 캡처',
                    style: Theme.of(ctx).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w800,
                        )),
                const SizedBox(height: AppSpacing.md),
                TextField(
                  decoration: InputDecoration(
                    prefixIcon: const Icon(Icons.link_rounded),
                    labelText: 'Zoom, Google Meet, Teams 링크',
                    errorText: errorText,
                  ),
                  keyboardType: TextInputType.url,
                  textInputAction: TextInputAction.done,
                  onChanged: (value) {
                    draftUrl = value;
                    if (errorText != null) {
                      setSheetState(() => errorText = null);
                    }
                  },
                ),
                const SizedBox(height: AppSpacing.lg),
                FilledButton.icon(
                  onPressed: () {
                    final url = draftUrl.trim();
                    final validationError = _validateMeetingUrl(url);
                    if (validationError != null) {
                      setSheetState(() => errorText = validationError);
                      return;
                    }

                    final meeting = _createOnlineMeeting(ref, url);
                    Navigator.of(ctx).pop();
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('${meeting.title}이 준비되었습니다.')),
                    );
                  },
                  icon: const Icon(Icons.smart_toy_outlined),
                  label: const Text('AI 기록 봇 준비'),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Meeting _createOnlineMeeting(WidgetRef ref, String sourceUrl) {
    final now = DateTime.now();
    final meeting = Meeting(
      id: 'meeting_${now.millisecondsSinceEpoch}',
      title: _onlineMeetingTitle(sourceUrl),
      createdAt: now,
      status: MeetingStatus.scheduled,
      sourceUrl: sourceUrl,
    );
    ref.read(meetingListProvider.notifier).addMeeting(meeting);
    return meeting;
  }

  void _showOnlineMeetingDetail(BuildContext context, Meeting meeting) {
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => Padding(
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
              meeting.title,
              style: Theme.of(ctx).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(meeting.sourceUrl ?? ''),
            const SizedBox(height: AppSpacing.lg),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                FilledButton.icon(
                  onPressed: () => _openOnlineMeeting(context, ctx, meeting),
                  icon: const Icon(Icons.open_in_new_rounded),
                  label: const Text('회의 열기'),
                ),
                OutlinedButton.icon(
                  onPressed: () => _addOnlineMeetingToCalendar(
                    context,
                    ctx,
                    meeting,
                  ),
                  icon: const Icon(Icons.event_available_rounded),
                  label: const Text('캘린더 추가'),
                ),
                OutlinedButton.icon(
                  onPressed: () {
                    Clipboard.setData(
                      ClipboardData(text: meeting.sourceUrl ?? ''),
                    );
                    Navigator.of(ctx).pop();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('회의 링크를 복사했습니다.')),
                    );
                  },
                  icon: const Icon(Icons.copy_rounded),
                  label: const Text('링크 복사'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openOnlineMeeting(
    BuildContext rootContext,
    BuildContext sheetContext,
    Meeting meeting,
  ) async {
    final sheetNavigator = Navigator.of(sheetContext);
    final messenger = ScaffoldMessenger.of(rootContext);
    final sourceUrl = meeting.sourceUrl;
    final uri = sourceUrl == null ? null : Uri.tryParse(sourceUrl);
    if (uri == null) {
      sheetNavigator.pop();
      messenger.showSnackBar(
        const SnackBar(content: Text('회의 링크를 열 수 없습니다.')),
      );
      return;
    }

    final launched = await launchUrl(
      uri,
      mode: LaunchMode.externalApplication,
    );

    sheetNavigator.pop();
    messenger.showSnackBar(
      SnackBar(
        content: Text(launched ? '회의 링크를 열었습니다.' : '회의 링크를 열 수 없습니다.'),
      ),
    );
  }

  Future<void> _addOnlineMeetingToCalendar(
    BuildContext rootContext,
    BuildContext sheetContext,
    Meeting meeting,
  ) async {
    final sheetNavigator = Navigator.of(sheetContext);
    final messenger = ScaffoldMessenger.of(rootContext);
    final uri = _buildGoogleCalendarUri(meeting);
    final launched = await launchUrl(
      uri,
      mode: LaunchMode.externalApplication,
    );

    sheetNavigator.pop();
    messenger.showSnackBar(
      SnackBar(
        content: Text(launched ? '캘린더에 추가할 수 있습니다.' : '캘린더를 열 수 없습니다.'),
      ),
    );
  }

  Uri _buildGoogleCalendarUri(Meeting meeting) {
    final start = meeting.createdAt.toUtc();
    final end = start.add(meeting.duration ?? const Duration(hours: 1));
    return Uri.https('calendar.google.com', '/calendar/render', {
      'action': 'TEMPLATE',
      'text': meeting.title,
      'details': meeting.sourceUrl ?? '',
      'location': meeting.sourceUrl ?? '',
      'dates': '${_calendarTimestamp(start)}/${_calendarTimestamp(end)}',
    });
  }

  String _calendarTimestamp(DateTime value) {
    final utc = value.toUtc();
    String two(int n) => n.toString().padLeft(2, '0');
    return '${utc.year}${two(utc.month)}${two(utc.day)}T'
        '${two(utc.hour)}${two(utc.minute)}${two(utc.second)}Z';
  }

  String? _validateMeetingUrl(String url) {
    if (url.isEmpty) return '회의 링크를 입력해주세요';
    final uri = Uri.tryParse(url);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
      return '올바른 회의 링크를 입력해주세요';
    }
    final host = uri.host.toLowerCase();
    final supported = host.contains('zoom.us') ||
        host.contains('meet.google.com') ||
        host.contains('teams.microsoft.com');
    return supported ? null : 'Zoom, Google Meet, Teams 링크만 지원합니다';
  }

  String _onlineMeetingTitle(String url) {
    final host = Uri.tryParse(url)?.host.toLowerCase() ?? '';
    if (host.contains('zoom.us')) return 'Zoom 회의';
    if (host.contains('meet.google.com')) return 'Google Meet 회의';
    if (host.contains('teams.microsoft.com')) return 'Microsoft Teams 회의';
    return '온라인 회의';
  }

  // 메뉴 버튼
  Widget _buildMenuButton(BuildContext context, WidgetRef ref) {
    final currentMode = ref.watch(themeModeProvider).mode;
    return PopupMenuButton<String>(
      tooltip: '메뉴',
      icon: Container(
        width: 38,
        height: 38,
        decoration: BoxDecoration(
          color: AppColors.of(context).surfaceAlt,
          shape: BoxShape.circle,
        ),
        child: const Icon(Icons.more_horiz, size: 20),
      ),
      onSelected: (value) {
        switch (value) {
          case 'search':
            context.push('/search');
          case 'toggle_theme':
            ref.read(themeModeProvider.notifier).setMode(
                  currentMode == AppThemeMode.dark
                      ? AppThemeMode.light
                      : AppThemeMode.dark,
                );
          case 'settings':
            context.push('/settings');
        }
      },
      itemBuilder: (_) => [
        const PopupMenuItem(
            value: 'search',
            child: _MenuItem(icon: Icons.search_rounded, label: '검색')),
        PopupMenuItem(
          value: 'toggle_theme',
          child: _MenuItem(
            icon: currentMode == AppThemeMode.dark
                ? Icons.light_mode_outlined
                : Icons.dark_mode_outlined,
            label: currentMode == AppThemeMode.dark ? '라이트 모드' : '다크 모드',
          ),
        ),
        const PopupMenuDivider(),
        const PopupMenuItem(
            value: 'settings',
            child: _MenuItem(icon: Icons.settings_outlined, label: '설정')),
      ],
    );
  }

  // 게스트 모드 배너
  Widget _buildGuestBanner(BuildContext context, WidgetRef ref) {
    final scheme = AppColors.of(context);
    return Container(
      margin: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
      padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md, vertical: AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.warningSoft.withAlpha(120),
        borderRadius: AppRadius.brMd,
        border: Border.all(color: AppColors.warning.withAlpha(60)),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline_rounded,
              size: 18, color: AppColors.warning),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              '게스트 모드 — 데이터가 24시간 후 삭제됩니다',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: scheme.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
            ),
          ),
          TextButton(
            onPressed: () => context.push('/register'),
            style: TextButton.styleFrom(
              padding: EdgeInsets.zero,
              minimumSize: const Size(0, 0),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: const Text('가입하기', style: TextStyle(fontSize: 13)),
          ),
        ],
      ),
    );
  }

  // REQ-HSYNC-003: 당겨서 새로 고침 처리
  Future<void> _onRefresh(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(meetingListProvider.notifier).refreshFromServer();
    } catch (_) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('서버 동기화 실패. 로컬 데이터를 표시합니다.')),
      );
    }
  }

  // REQ-HSYNC-005: 롱프레스 시 삭제 확인 다이얼로그
  Future<void> _onLongPress(
      BuildContext context, WidgetRef ref, String meetingId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('미팅 삭제'),
        content: const Text('이 미팅을 삭제하시겠습니까? 서버에서도 삭제됩니다.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('취소')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.error),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      await _deleteMeeting(context, ref, meetingId);
    }
  }

  Future<void> _deleteMeeting(
      BuildContext context, WidgetRef ref, String meetingId) async {
    try {
      final historyApi = ref.read(historyApiProvider);
      await historyApi.delete(meetingId);
    } catch (_) {
      // 서버 삭제 실패는 무시
    } finally {
      await ref.read(meetingListProvider.notifier).removeMeeting(meetingId);
    }
  }
}

class _HeroBadge extends StatelessWidget {
  final IconData icon;
  final String label;
  const _HeroBadge({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: Colors.white.withAlpha(28),
        borderRadius: AppRadius.brPill,
        border: Border.all(color: Colors.white.withAlpha(42)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: Colors.white, size: 16),
          const SizedBox(width: AppSpacing.xs),
          Text(label,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  )),
        ],
      ),
    );
  }
}

class _ShortcutTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _ShortcutTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    return Material(
      color: scheme.surface,
      borderRadius: AppRadius.brMd,
      child: InkWell(
        borderRadius: AppRadius.brMd,
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            borderRadius: AppRadius.brMd,
            border: Border.all(color: scheme.border),
          ),
          child: Row(
            children: [
              Icon(icon, color: scheme.primary),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: Theme.of(context)
                            .textTheme
                            .labelLarge
                            ?.copyWith(fontWeight: FontWeight.w800)),
                    Text(subtitle,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: scheme.textSecondary,
                            )),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 메뉴 항목 위젯
class _MenuItem extends StatelessWidget {
  final IconData icon;
  final String label;
  const _MenuItem({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    return Row(
      children: [
        Icon(icon, size: 20, color: scheme.textSecondary),
        const SizedBox(width: AppSpacing.md),
        Text(label, style: Theme.of(context).textTheme.bodyMedium),
      ],
    );
  }
}
