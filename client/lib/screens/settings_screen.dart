// 설정 화면 — 테마 전환, 계정, 정보
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/providers/theme_mode_provider.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeState = ref.watch(themeModeProvider);
    final authState = ref.watch(authStateProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('설정')),
      body: ListView(
        children: [
          const _SectionHeader('외관'),
          // 테마 모드 선택
          ListTile(
            leading: const Icon(Icons.palette_outlined),
            title: const Text('테마'),
            subtitle: Text(themeState.mode.label),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => _showThemePicker(context, ref),
          ),

          const _SectionHeader('데이터'),
          ListTile(
            leading: const Icon(Icons.search_rounded),
            title: const Text('검색'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => context.push('/search'),
          ),
          ListTile(
            leading: const Icon(Icons.groups_rounded),
            title: const Text('팀 관리'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => context.push('/teams'),
          ),
          ListTile(
            leading: const Icon(Icons.description_outlined),
            title: const Text('양식 관리'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => context.push('/templates'),
          ),
          ListTile(
            leading: const Icon(Icons.menu_book_rounded),
            title: const Text('사용자 사전'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => context.push('/vocabulary'),
          ),
          ListTile(
            leading: const Icon(Icons.record_voice_over_outlined),
            title: const Text('화자 프로필'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => context.push('/speakers'),
          ),
          ListTile(
            leading: const Icon(Icons.cloud_download_outlined),
            title: const Text('오프라인 STT 모델'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => context.push('/model-download'),
          ),

          if (authState.isAuthenticated || authState.isGuest) ...[
            const _SectionHeader('계정'),
            if (authState.isAuthenticated)
              ListTile(
                leading: const Icon(Icons.person_outline_rounded),
                title: Text(authState.user?.displayName ?? '사용자'),
                subtitle: Text(authState.user?.email ?? ''),
              )
            else
              const ListTile(
                leading: Icon(Icons.person_outline_rounded),
                title: Text('게스트 모드'),
                subtitle: Text('데이터가 24시간 후 삭제됩니다'),
              ),
            ListTile(
              leading: const Icon(Icons.logout_rounded, color: AppColors.error),
              title: Text(authState.isGuest ? '게스트 종료' : '로그아웃'),
              onTap: () => _confirmLogout(context, ref),
            ),
          ],

          const _SectionHeader('정보'),
          const ListTile(
            leading: Icon(Icons.info_outline_rounded),
            title: Text('버전'),
            trailing: Text('1.0.0'),
          ),
        ],
      ),
    );
  }

  void _showThemePicker(BuildContext context, WidgetRef ref) {
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) {
        final current = ref.read(themeModeProvider).mode;
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Text('테마 선택',
                    style: Theme.of(context).textTheme.titleMedium),
              ),
              for (final mode in AppThemeMode.values)
                ListTile(
                  leading: Icon(current == mode
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked),
                  title: Text(mode.label),
                  onTap: () {
                    ref.read(themeModeProvider.notifier).setMode(mode);
                    Navigator.of(ctx).pop();
                  },
                ),
              const SizedBox(height: AppSpacing.sm),
            ],
          ),
        );
      },
    );
  }

  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    final isGuest = ref.read(authStateProvider).isGuest;
    final title = isGuest ? '게스트 종료' : '로그아웃';
    final message = isGuest
        ? '게스트 모드를 종료하고 로그인 화면으로 이동합니다.\n저장된 데이터는 24시간 후 삭제됩니다.'
        : '로그아웃하시겠습니까?';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('취소')),
          FilledButton(
              onPressed: () => Navigator.of(ctx).pop(true), child: Text(title)),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      await ref.read(authStateProvider.notifier).logout();
    }
  }
}

/// 섹션 헤더 — 소문자 라벨
class _SectionHeader extends StatelessWidget {
  final String text;
  const _SectionHeader(this.text);

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(
          AppSpacing.xl, AppSpacing.xl, AppSpacing.xl, AppSpacing.sm),
      child: Text(
        text,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: scheme.textTertiary,
              letterSpacing: 0.5,
            ),
      ),
    );
  }
}
