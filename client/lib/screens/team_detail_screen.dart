// 팀 상세 화면 (SPEC-TEAM-001 REQ-TEAM-006)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/providers/team_provider.dart';
import 'package:voice_to_textnote/services/team_api.dart';

class TeamDetailScreen extends ConsumerStatefulWidget {
  final String teamId;

  const TeamDetailScreen({super.key, required this.teamId});

  @override
  ConsumerState<TeamDetailScreen> createState() => _TeamDetailScreenState();
}

class _TeamDetailScreenState extends ConsumerState<TeamDetailScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // 현재 로그인한 사용자 ID (임시: 실제 앱에서는 auth provider에서 가져옴)
  // @MX:TODO: auth provider 연동 후 실제 사용자 ID로 교체 필요
  String? _currentUserId;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // 현재 사용자의 팀 내 역할 확인
  String? _getCurrentUserRole(TeamDetail detail) {
    if (_currentUserId == null) return null;
    try {
      final member =
          detail.members.firstWhere((m) => m.userId == _currentUserId);
      return member.role;
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final teamAsync = ref.watch(teamDetailProvider(widget.teamId));

    return teamAsync.when(
      loading: () => Scaffold(
        appBar: AppBar(title: const Text('팀 상세')),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (error, stack) => Scaffold(
        appBar: AppBar(title: const Text('팀 상세')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.red),
              const SizedBox(height: 16),
              const Text('팀 정보를 불러오지 못했습니다'),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () =>
                    ref.invalidate(teamDetailProvider(widget.teamId)),
                child: const Text('다시 시도'),
              ),
            ],
          ),
        ),
      ),
      data: (detail) {
        final currentRole = _getCurrentUserRole(detail);
        final isAdmin = currentRole == 'admin';

        return Scaffold(
          appBar: AppBar(
            title: Text(detail.name),
            centerTitle: true,
            actions: [
              // 관리자만 팀 편집 버튼 표시
              if (isAdmin)
                IconButton(
                  icon: const Icon(Icons.edit_outlined),
                  tooltip: '팀 편집',
                  onPressed: () => _showEditTeamDialog(context, detail),
                ),
            ],
            bottom: TabBar(
              controller: _tabController,
              tabs: const [
                Tab(text: '멤버'),
                Tab(text: '공유 미팅'),
              ],
            ),
          ),
          body: TabBarView(
            controller: _tabController,
            children: [
              // 멤버 탭
              _MembersTab(
                detail: detail,
                isAdmin: isAdmin,
                currentUserId: _currentUserId,
                onInvite: () => _showInviteMemberDialog(context, detail.id),
                onRoleChange: (member, newRole) =>
                    _changeRole(context, detail.id, member, newRole),
                onRemove: (member) => _removeMember(context, detail.id, member),
                onLeave: () => _leaveTeam(context, detail),
                onDelete: isAdmin
                    ? () => _deleteTeam(context, detail)
                    : null,
              ),
              // 공유 미팅 탭
              _TeamMeetingsTab(teamId: detail.id),
            ],
          ),
        );
      },
    );
  }

  // 팀 편집 다이얼로그
  Future<void> _showEditTeamDialog(
      BuildContext context, TeamDetail detail) async {
    final nameController = TextEditingController(text: detail.name);
    final descController = TextEditingController(text: detail.description ?? '');
    final formKey = GlobalKey<FormState>();

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('팀 편집'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: nameController,
                decoration: const InputDecoration(
                  labelText: '팀 이름 *',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return '팀 이름을 입력하세요';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: descController,
                decoration: const InputDecoration(
                  labelText: '설명 (선택)',
                  border: OutlineInputBorder(),
                ),
                maxLines: 2,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () async {
              if (!formKey.currentState!.validate()) return;
              Navigator.of(dialogContext).pop();
              await _updateTeam(
                context,
                detail.id,
                name: nameController.text.trim(),
                description: descController.text.trim().isEmpty
                    ? null
                    : descController.text.trim(),
              );
            },
            child: const Text('저장'),
          ),
        ],
      ),
    );

    nameController.dispose();
    descController.dispose();
  }

  // 팀 정보 수정 API 호출
  Future<void> _updateTeam(
    BuildContext context,
    String teamId, {
    String? name,
    String? description,
  }) async {
    try {
      final api = ref.read(teamApiProvider);
      await api.updateTeam(teamId, name: name, description: description);
      ref.invalidate(teamDetailProvider(widget.teamId));

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('팀 정보가 수정되었습니다')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('팀 정보 수정에 실패했습니다')),
        );
      }
    }
  }

  // 멤버 초대 다이얼로그
  Future<void> _showInviteMemberDialog(
      BuildContext context, String teamId) async {
    final emailController = TextEditingController();
    String selectedRole = 'member';
    final formKey = GlobalKey<FormState>();

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('멤버 초대'),
          content: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: emailController,
                  decoration: const InputDecoration(
                    labelText: '이메일 *',
                    hintText: '초대할 사용자의 이메일',
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.emailAddress,
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return '이메일을 입력하세요';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                // 역할 선택 드롭다운
                DropdownButtonFormField<String>(
                  initialValue: selectedRole,
                  decoration: const InputDecoration(
                    labelText: '역할',
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'admin', child: Text('관리자')),
                    DropdownMenuItem(value: 'member', child: Text('멤버')),
                    DropdownMenuItem(value: 'viewer', child: Text('뷰어')),
                  ],
                  onChanged: (value) {
                    if (value != null) {
                      setState(() => selectedRole = value);
                    }
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: () async {
                if (!formKey.currentState!.validate()) return;
                Navigator.of(dialogContext).pop();
                await _inviteMember(
                  context,
                  teamId,
                  email: emailController.text.trim(),
                  role: selectedRole,
                );
              },
              child: const Text('초대'),
            ),
          ],
        ),
      ),
    );

    emailController.dispose();
  }

  // 멤버 초대 API 호출
  Future<void> _inviteMember(
    BuildContext context,
    String teamId, {
    required String email,
    required String role,
  }) async {
    try {
      final api = ref.read(teamApiProvider);
      await api.inviteMember(teamId, email: email, role: role);
      ref.invalidate(teamDetailProvider(widget.teamId));

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$email 님을 초대했습니다')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('멤버 초대에 실패했습니다')),
        );
      }
    }
  }

  // 역할 변경 API 호출
  Future<void> _changeRole(
    BuildContext context,
    String teamId,
    TeamMember member,
    String newRole,
  ) async {
    try {
      final api = ref.read(teamApiProvider);
      await api.updateMemberRole(teamId, member.userId, role: newRole);
      ref.invalidate(teamDetailProvider(widget.teamId));

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${member.displayName}의 역할이 변경되었습니다')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('역할 변경에 실패했습니다')),
        );
      }
    }
  }

  // 멤버 제거 API 호출
  Future<void> _removeMember(
    BuildContext context,
    String teamId,
    TeamMember member,
  ) async {
    // 확인 다이얼로그
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('멤버 제거'),
        content: Text('${member.displayName}을(를) 팀에서 제거할까요?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('제거'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final api = ref.read(teamApiProvider);
      await api.removeMember(teamId, member.userId);
      ref.invalidate(teamDetailProvider(widget.teamId));

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${member.displayName}이(가) 제거되었습니다')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('멤버 제거에 실패했습니다')),
        );
      }
    }
  }

  // 팀 나가기 (비관리자의 자기 자신 제거)
  Future<void> _leaveTeam(BuildContext context, TeamDetail detail) async {
    if (_currentUserId == null) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('팀 나가기'),
        content: Text('"${detail.name}" 팀을 나갈까요?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('나가기'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final api = ref.read(teamApiProvider);
      await api.removeMember(detail.id, _currentUserId!);

      if (context.mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('팀을 나갔습니다')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('팀 나가기에 실패했습니다')),
        );
      }
    }
  }

  // 팀 삭제 (관리자만)
  Future<void> _deleteTeam(BuildContext context, TeamDetail detail) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('팀 삭제'),
        content: Text(
          '"${detail.name}" 팀을 삭제할까요?\n삭제된 팀은 복구할 수 없습니다.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final api = ref.read(teamApiProvider);
      await api.deleteTeam(detail.id);

      if (context.mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('"${detail.name}" 팀이 삭제되었습니다')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('팀 삭제에 실패했습니다')),
        );
      }
    }
  }
}

// 멤버 탭 위젯
class _MembersTab extends StatelessWidget {
  final TeamDetail detail;
  final bool isAdmin;
  final String? currentUserId;
  final VoidCallback onInvite;
  final Function(TeamMember, String) onRoleChange;
  final Function(TeamMember) onRemove;
  final VoidCallback onLeave;
  final VoidCallback? onDelete;

  const _MembersTab({
    required this.detail,
    required this.isAdmin,
    required this.currentUserId,
    required this.onInvite,
    required this.onRoleChange,
    required this.onRemove,
    required this.onLeave,
    this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // 팀 정보 헤더
        if (detail.description != null && detail.description!.isNotEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            color: Theme.of(context).colorScheme.surfaceContainerLow,
            child: Text(
              detail.description!,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
        // 멤버 수 + 초대 버튼
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              Text(
                '멤버 ${detail.memberCount}명',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const Spacer(),
              // 관리자만 초대 버튼 표시
              if (isAdmin)
                FilledButton.icon(
                  onPressed: onInvite,
                  icon: const Icon(Icons.person_add_outlined, size: 18),
                  label: const Text('멤버 초대'),
                ),
            ],
          ),
        ),
        const Divider(height: 1),
        // 멤버 목록
        Expanded(
          child: ListView.builder(
            itemCount: detail.members.length,
            itemBuilder: (context, index) {
              final member = detail.members[index];
              final isSelf = member.userId == currentUserId;

              return _MemberListTile(
                member: member,
                isSelf: isSelf,
                isAdmin: isAdmin,
                onRoleChange: isAdmin && !isSelf
                    ? (newRole) => onRoleChange(member, newRole)
                    : null,
                onRemove: isAdmin && !isSelf ? () => onRemove(member) : null,
              );
            },
          ),
        ),
        // 하단 액션 버튼
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              // 팀 나가기 버튼 (비관리자만)
              if (!isAdmin)
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onLeave,
                    icon: const Icon(Icons.exit_to_app),
                    label: const Text('팀 나가기'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              // 팀 삭제 버튼 (관리자만)
              if (isAdmin && onDelete != null)
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onDelete,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('팀 삭제'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

// 멤버 목록 항목 위젯
class _MemberListTile extends StatelessWidget {
  final TeamMember member;
  final bool isSelf;
  final bool isAdmin;
  final Function(String)? onRoleChange;
  final VoidCallback? onRemove;

  const _MemberListTile({
    required this.member,
    required this.isSelf,
    required this.isAdmin,
    this.onRoleChange,
    this.onRemove,
  });

  // 역할에 따른 배지 색상
  Color _roleBadgeColor(BuildContext context) {
    switch (member.role) {
      case 'admin':
        return Theme.of(context).colorScheme.primaryContainer;
      case 'viewer':
        return Theme.of(context).colorScheme.surfaceContainerHighest;
      default:
        return Theme.of(context).colorScheme.secondaryContainer;
    }
  }

  // 역할 한글 표시
  String _roleLabel() {
    switch (member.role) {
      case 'admin':
        return '관리자';
      case 'viewer':
        return '뷰어';
      default:
        return '멤버';
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: CircleAvatar(
        child: Text(
          member.displayName.isNotEmpty
              ? member.displayName[0].toUpperCase()
              : '?',
        ),
      ),
      title: Row(
        children: [
          Text(member.displayName),
          if (isSelf) ...[
            const SizedBox(width: 6),
            const Text('(나)', style: TextStyle(color: Colors.grey, fontSize: 12)),
          ],
        ],
      ),
      subtitle: Text(member.email, style: const TextStyle(fontSize: 12)),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // 역할 배지
          if (isAdmin && onRoleChange != null)
            // 관리자는 드롭다운으로 역할 변경 가능
            DropdownButton<String>(
              value: member.role,
              underline: const SizedBox.shrink(),
              items: const [
                DropdownMenuItem(value: 'admin', child: Text('관리자')),
                DropdownMenuItem(value: 'member', child: Text('멤버')),
                DropdownMenuItem(value: 'viewer', child: Text('뷰어')),
              ],
              onChanged: (newRole) {
                if (newRole != null && newRole != member.role) {
                  onRoleChange!(newRole);
                }
              },
            )
          else
            // 일반 멤버는 배지만 표시
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _roleBadgeColor(context),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                _roleLabel(),
                style: const TextStyle(fontSize: 12),
              ),
            ),
          // 제거 버튼 (관리자만, 자기 자신 제외)
          if (onRemove != null) ...[
            const SizedBox(width: 4),
            IconButton(
              icon: const Icon(Icons.remove_circle_outline, color: Colors.red),
              tooltip: '제거',
              onPressed: onRemove,
            ),
          ],
        ],
      ),
    );
  }
}

// 팀 공유 미팅 탭
class _TeamMeetingsTab extends ConsumerWidget {
  final String teamId;

  const _TeamMeetingsTab({required this.teamId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // @MX:NOTE: 팀 미팅 목록은 별도 FutureProvider 없이 직접 조회
    // 복잡한 캐싱이 필요한 경우 별도 provider 추가 고려
    final meetingsAsync = ref.watch(
      _teamMeetingsFutureProvider(teamId),
    );

    return meetingsAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, __) => const Center(child: Text('미팅 목록을 불러오지 못했습니다')),
      data: (meetings) => meetings.isEmpty
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.folder_open, size: 48, color: Colors.grey),
                  SizedBox(height: 16),
                  Text(
                    '공유된 미팅이 없습니다',
                    style: TextStyle(color: Colors.grey),
                  ),
                ],
              ),
            )
          : ListView.builder(
              itemCount: meetings.length,
              itemBuilder: (context, index) {
                final meeting = meetings[index];
                return ListTile(
                  leading: const Icon(Icons.article_outlined),
                  title: Text(meeting['title'] as String? ?? '제목 없음'),
                  subtitle: Text(meeting['shared_at'] as String? ?? ''),
                );
              },
            ),
    );
  }
}

// 팀 미팅 목록을 위한 내부 provider
final _teamMeetingsFutureProvider =
    FutureProvider.family<List<Map<String, dynamic>>, String>(
        (ref, teamId) async {
  final api = ref.watch(teamApiProvider);
  return api.getTeamMeetings(teamId);
});
