// 미팅 팀 공유 다이얼로그 위젯 (SPEC-TEAM-001 REQ-TEAM-006)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/providers/team_provider.dart';
import 'package:voice_to_textnote/services/team_api.dart';

// 미팅을 팀에 공유/해제하는 다이얼로그
// result_screen.dart 등에서 showDialog로 사용
// @MX:ANCHOR: 미팅 공유 기능의 단일 UI 진입점
// @MX:REASON: 공유 상태 관리 및 API 호출을 한 곳에서 담당
class TeamShareDialog extends ConsumerStatefulWidget {
  // 공유할 미팅의 task_id
  final String taskId;

  // 현재 이미 공유된 팀 ID 목록 (초기 선택 상태 설정에 사용)
  final Set<String> initiallySharedTeamIds;

  const TeamShareDialog({
    super.key,
    required this.taskId,
    this.initiallySharedTeamIds = const {},
  });

  @override
  ConsumerState<TeamShareDialog> createState() => _TeamShareDialogState();
}

class _TeamShareDialogState extends ConsumerState<TeamShareDialog> {
  // 현재 선택된 팀 ID 집합 (공유 중인 팀)
  late Set<String> _sharedTeamIds;

  // 변경 중인 팀 ID (로딩 표시용)
  final Set<String> _loadingTeamIds = {};

  @override
  void initState() {
    super.initState();
    _sharedTeamIds = Set.from(widget.initiallySharedTeamIds);
  }

  // 공유 토글 처리
  Future<void> _toggleShare(Team team) async {
    final isCurrentlyShared = _sharedTeamIds.contains(team.id);

    setState(() => _loadingTeamIds.add(team.id));

    try {
      final api = ref.read(teamApiProvider);

      if (isCurrentlyShared) {
        // 공유 해제
        await api.unshareMeeting(widget.taskId, team.id);
        setState(() => _sharedTeamIds.remove(team.id));
      } else {
        // 공유
        await api.shareMeeting(widget.taskId, team.id);
        setState(() => _sharedTeamIds.add(team.id));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              isCurrentlyShared ? '공유 해제에 실패했습니다' : '공유에 실패했습니다',
            ),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loadingTeamIds.remove(team.id));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final teamsAsync = ref.watch(teamListProvider);

    return AlertDialog(
      title: const Text('팀에 공유'),
      content: SizedBox(
        width: double.maxFinite,
        child: teamsAsync.when(
          loading: () => const SizedBox(
            height: 100,
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (_, __) => const SizedBox(
            height: 100,
            child: Center(child: Text('팀 목록을 불러오지 못했습니다')),
          ),
          data: (teams) => teams.isEmpty
              ? SizedBox(
                  height: 100,
                  child: Center(
                    child: Text(
                      '속한 팀이 없습니다',
                      style: TextStyle(color: Theme.of(context).colorScheme.outline),
                    ),
                  ),
                )
              : ListView.builder(
                  shrinkWrap: true,
                  itemCount: teams.length,
                  itemBuilder: (context, index) {
                    final team = teams[index];
                    final isShared = _sharedTeamIds.contains(team.id);
                    final isLoading = _loadingTeamIds.contains(team.id);

                    return CheckboxListTile(
                      value: isShared,
                      // 로딩 중에는 변경 불가
                      onChanged: isLoading
                          ? null
                          : (_) => _toggleShare(team),
                      title: Text(team.name),
                      subtitle: team.description != null &&
                              team.description!.isNotEmpty
                          ? Text(
                              team.description!,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            )
                          : null,
                      secondary: isLoading
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : CircleAvatar(
                              radius: 16,
                              backgroundColor: Theme.of(context)
                                  .colorScheme
                                  .primaryContainer,
                              child: Text(
                                team.name.isNotEmpty
                                    ? team.name[0].toUpperCase()
                                    : 'T',
                                style: const TextStyle(fontSize: 12),
                              ),
                            ),
                      controlAffinity: ListTileControlAffinity.trailing,
                    );
                  },
                ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('닫기'),
        ),
      ],
    );
  }
}
