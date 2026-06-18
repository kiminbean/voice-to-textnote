// 홈 화면 - 미팅 목록 표시 (모던 미니멀)
// @MX:NOTE: SPEC-TMPL/SEARCH/TEAM/HISTSYNC/GUEST 통합 진입점
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/providers/theme_mode_provider.dart';
import 'package:voice_to_textnote/services/history_api.dart';
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
          // 본문
          meetingsAsync.when(
            loading: () => SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
              sliver: SliverList.builder(itemCount: 3, itemBuilder: (_, __) => const ShimmerCard()),
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
                    padding: const EdgeInsets.fromLTRB(
                        AppSpacing.lg, AppSpacing.sm, AppSpacing.lg, AppSpacing.xxxl),
                    sliver: SliverList.builder(
                      itemCount: meetings.length,
                      itemBuilder: (context, index) {
                        final meeting = meetings[index];
                        return Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                          child: MeetingCard(
                            meeting: meeting,
                            onTap: () => context.push('/result/${meeting.id}'),
                            onLongPress: () => _onLongPress(context, ref, meeting.id),
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
        label: const Text('녹음'),
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
          '회의 기록',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w700,
                letterSpacing: -0.3,
              ),
        ),
      ],
    );
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
        const PopupMenuItem(value: 'search', child: _MenuItem(icon: Icons.search_rounded, label: '검색')),
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
        const PopupMenuItem(value: 'settings', child: _MenuItem(icon: Icons.settings_outlined, label: '설정')),
      ],
    );
  }

  // 게스트 모드 배너
  Widget _buildGuestBanner(BuildContext context, WidgetRef ref) {
    final scheme = AppColors.of(context);
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.warningSoft.withAlpha(120),
        borderRadius: AppRadius.brMd,
        border: Border.all(color: AppColors.warning.withAlpha(60)),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline_rounded, size: 18, color: AppColors.warning),
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
  Future<void> _onLongPress(BuildContext context, WidgetRef ref, String meetingId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('미팅 삭제'),
        content: const Text('이 미팅을 삭제하시겠습니까? 서버에서도 삭제됩니다.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('취소')),
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

  Future<void> _deleteMeeting(BuildContext context, WidgetRef ref, String meetingId) async {
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
