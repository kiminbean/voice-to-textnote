// 팀 목록 화면 (SPEC-TEAM-001 REQ-TEAM-006)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/providers/team_provider.dart';
import 'package:voice_to_textnote/services/team_api.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';

class TeamListScreen extends ConsumerWidget {
  const TeamListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final teamsAsync = ref.watch(teamListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('팀 관리'),
        centerTitle: true,
      ),
      body: teamsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) => EmptyStateWidget(
          icon: Icons.cloud_off_rounded,
          title: '팀 목록을 불러오지 못했습니다',
          actionLabel: '다시 시도',
          onAction: () => ref.invalidate(teamListProvider),
        ),
        data: (teams) => teams.isEmpty
            ? const EmptyStateWidget(
                icon: Icons.groups_outlined,
                title: '속한 팀이 없습니다',
                subtitle: '아래 버튼을 눌러 팀을 만드세요',
              )
            : RefreshIndicator(
                onRefresh: () async => ref.invalidate(teamListProvider),
                child: ListView.builder(
                  padding: const EdgeInsets.all(8),
                  itemCount: teams.length,
                  itemBuilder: (context, index) {
                    return _TeamCard(
                      team: teams[index],
                      onTap: () => context.push('/teams/${teams[index].id}'),
                    );
                  },
                ),
              ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showCreateTeamDialog(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('팀 생성'),
      ),
    );
  }

  // 팀 생성 다이얼로그 표시
  Future<void> _showCreateTeamDialog(
      BuildContext context, WidgetRef ref) async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => _CreateTeamDialog(
        onCreate: (name, description) => _createTeam(
          context,
          ref,
          name: name,
          description: description,
        ),
      ),
    );
  }

  // 팀 생성 API 호출
  Future<void> _createTeam(
    BuildContext context,
    WidgetRef ref, {
    required String name,
    String? description,
  }) async {
    try {
      final api = ref.read(teamApiProvider);
      await api.createTeam(name: name, description: description);

      // 목록 갱신
      ref.invalidate(teamListProvider);

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('팀 "$name"이 생성되었습니다')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('팀 생성에 실패했습니다')),
        );
      }
    }
  }
}

class _CreateTeamDialog extends StatefulWidget {
  final Future<void> Function(String name, String? description) onCreate;

  const _CreateTeamDialog({required this.onCreate});

  @override
  State<_CreateTeamDialog> createState() => _CreateTeamDialogState();
}

class _CreateTeamDialogState extends State<_CreateTeamDialog> {
  final _nameController = TextEditingController();
  final _descController = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  @override
  void dispose() {
    _nameController.dispose();
    _descController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    final name = _nameController.text.trim();
    final rawDescription = _descController.text.trim();
    final description = rawDescription.isEmpty ? null : rawDescription;

    Navigator.of(context).pop();
    await widget.onCreate(name, description);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('새 팀 만들기'),
      content: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextFormField(
              controller: _nameController,
              decoration: const InputDecoration(
                labelText: '팀 이름 *',
                hintText: '팀 이름을 입력하세요',
                border: OutlineInputBorder(),
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return '팀 이름을 입력하세요';
                }
                return null;
              },
              autofocus: true,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _descController,
              decoration: const InputDecoration(
                labelText: '설명 (선택)',
                hintText: '팀에 대한 설명을 입력하세요',
                border: OutlineInputBorder(),
              ),
              maxLines: 2,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('취소'),
        ),
        FilledButton(
          onPressed: _submit,
          child: const Text('만들기'),
        ),
      ],
    );
  }
}

// 팀 카드 위젯
class _TeamCard extends StatelessWidget {
  final Team team;
  final VoidCallback onTap;

  const _TeamCard({required this.team, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 4),
      child: ListTile(
        onTap: onTap,
        leading: CircleAvatar(
          backgroundColor: theme.colorScheme.primaryContainer,
          child: Text(
            team.name.isNotEmpty ? team.name[0].toUpperCase() : 'T',
            style: TextStyle(
              color: theme.colorScheme.onPrimaryContainer,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        title: Text(
          team.name,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: team.description != null && team.description!.isNotEmpty
            ? Text(
                team.description!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              )
            : null,
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.people_outline,
                size: 16, color: Theme.of(context).colorScheme.outline),
            const SizedBox(width: 4),
            Text(
              '${team.memberCount}명',
              style: TextStyle(
                  color: Theme.of(context).colorScheme.outline, fontSize: 13),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }
}
