// 협업 참여자 Presence 표시 바
// SPEC-COLLAB-001: AC-042 (REQ-COLLAB-042)
import 'package:flutter/material.dart';
import 'package:voice_to_textnote/services/collab_socket_service.dart';

class CollabPresenceBar extends StatelessWidget {
  final List<CollabUser> activeUsers;

  const CollabPresenceBar({super.key, required this.activeUsers});

  @override
  Widget build(BuildContext context) {
    if (activeUsers.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Row(
        children: [
          _buildAvatars(context),
          const SizedBox(width: 8),
          Text(
            '${activeUsers.length}명 편집 중',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Colors.grey[600],
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildAvatars(BuildContext context) {
    const maxVisible = 5;
    final visible = activeUsers.take(maxVisible).toList();
    final overflow = activeUsers.length - maxVisible;
    final totalWidth = (visible.length * 20.0) + (overflow > 0 ? 20.0 : 14.0);

    return SizedBox(
      height: 32,
      width: totalWidth,
      child: Stack(
        children: [
          for (int i = visible.length - 1; i >= 0; i--)
            Positioned(
              left: i * 20.0,
              child: _UserAvatar(user: visible[i]),
            ),
          if (overflow > 0)
            Positioned(
              left: visible.length * 20.0,
              child: CircleAvatar(
                radius: 14,
                backgroundColor: Colors.grey[300],
                child: Text(
                  '+$overflow',
                  style: const TextStyle(fontSize: 10, color: Colors.black87),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _UserAvatar extends StatelessWidget {
  final CollabUser user;

  const _UserAvatar({required this.user});

  @override
  Widget build(BuildContext context) {
    final color = _parseColor(user.color);
    final initial = user.displayName.isNotEmpty ? user.displayName[0] : '?';

    return CircleAvatar(
      radius: 14,
      backgroundColor: color,
      child: Text(
        initial.toUpperCase(),
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.bold,
          color: Colors.white,
        ),
      ),
    );
  }

  Color _parseColor(String hex) {
    if (hex.isEmpty) return Colors.blue;
    try {
      final cleaned = hex.replaceFirst('#', '');
      if (cleaned.length == 6) {
        return Color(int.parse('FF$cleaned', radix: 16));
      }
    } catch (_) {}
    return Colors.blue;
  }
}
