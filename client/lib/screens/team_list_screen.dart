// 팀 목록 화면 (SPEC-TEAM-001 REQ-TEAM-006)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/providers/team_provider.dart';
import 'package:voice_to_textnote/services/team_api.dart';

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
        error: (error, stack) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.red),
              const SizedBox(height: 16),
              Text(
                '팀 목록을 불러오지 못했습니다',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => ref.invalidate(teamListProvider),
                child: const Text('다시 시도'),
              ),
            ],
          ),
        ),
        data: (teams) => teams.isEmpty
            ? const Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.groups_outlined, size: 64, color: Colors.grey),
                    SizedBox(height: 16),
                    Text(
                      '속한 팀이 없습니다',
                      style: TextStyle(color: Colors.grey, fontSize: 16),
                    ),
                    SizedBox(height: 8),
                    Text(
                      '아래 버튼을 눌러 팀을 만드세요',
                      style: TextStyle(color: Colors.grey, fontSize: 14),
                    ),
                  ],
                ),
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
    final nameController = TextEditingController();
    final descController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('새 팀 만들기'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: nameController,
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
                controller: descController,
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
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () async {
              if (!formKey.currentState!.validate()) return;

              Navigator.of(dialogContext).pop();
              await _createTeam(
                context,
                ref,
                name: nameController.text.trim(),
                description: descController.text.trim().isEmpty
                    ? null
                    : descController.text.trim(),
              );
            },
            child: const Text('만들기'),
          ),
        ],
      ),
    );

    nameController.dispose();
    descController.dispose();
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
            const Icon(Icons.people_outline, size: 16, color: Colors.grey),
            const SizedBox(width: 4),
            Text(
              '${team.memberCount}명',
              style: const TextStyle(color: Colors.grey, fontSize: 13),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }
}
