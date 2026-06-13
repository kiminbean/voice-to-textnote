// SPEC-COLLAB-001: 활성 사용자 presence 표시 위젯
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/providers/collab_provider.dart';
import 'package:voice_to_textnote/services/collab_service.dart';

class PresenceOverlay extends ConsumerWidget {
  const PresenceOverlay({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final presence = ref.watch(
      collabProvider.select((s) => s.presence),
    );

    if (presence.isEmpty) return const SizedBox.shrink();

    final visibleUsers = presence.take(5).toList();
    final extraCount = presence.length - visibleUsers.length;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          ...visibleUsers.map((u) => Padding(
                padding: const EdgeInsets.only(right: 4),
                child: _PresenceAvatar(user: u),
              )),
          if (extraCount > 0)
            Padding(
              padding: const EdgeInsets.only(left: 4),
              child: Text(
                '+$extraCount',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ),
        ],
      ),
    );
  }
}

class _PresenceAvatar extends StatelessWidget {
  final PresenceUser user;

  const _PresenceAvatar({required this.user});

  @override
  Widget build(BuildContext context) {
    final initial = user.displayName.isNotEmpty
        ? user.displayName[0].toUpperCase()
        : '?';
    final color = _colorForUserId(user.userId, context);

    return Tooltip(
      message: user.displayName,
      child: CircleAvatar(
        radius: 14,
        backgroundColor: color,
        backgroundImage:
            user.avatarUrl != null && user.avatarUrl!.isNotEmpty
                ? NetworkImage(user.avatarUrl!)
                : null,
        child: user.avatarUrl == null || user.avatarUrl!.isEmpty
            ? Text(
                initial,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: ThemeData.estimateBrightnessForColor(color) ==
                              Brightness.dark
                          ? Colors.white
                          : Colors.black,
                    ),
              )
            : null,
      ),
    );
  }

  Color _colorForUserId(String userId, BuildContext context) {
    final palette = [
      Colors.red.shade300,
      Colors.blue.shade300,
      Colors.green.shade300,
      Colors.orange.shade300,
      Colors.purple.shade300,
      Colors.teal.shade300,
    ];
    final hash = userId.hashCode.abs();
    return palette[hash % palette.length];
  }
}
