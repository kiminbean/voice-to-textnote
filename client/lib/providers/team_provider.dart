// 팀 상태 프로바이더 (SPEC-TEAM-001 REQ-TEAM-006)
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/services/team_api.dart';

// 팀 목록 프로바이더
// @MX:ANCHOR: team_list_screen, team_share_dialog에서 참조됨
// @MX:REASON: 사용자가 속한 팀 목록의 단일 진입점
final teamListProvider = FutureProvider<List<Team>>((ref) async {
  final api = ref.watch(teamApiProvider);
  return api.getTeams();
});

// 팀 상세 프로바이더 (팀 ID를 파라미터로 사용)
// @MX:NOTE: teamId를 key로 사용하는 FutureProvider.family 패턴
final teamDetailProvider =
    FutureProvider.family<TeamDetail, String>((ref, teamId) async {
  final api = ref.watch(teamApiProvider);
  return api.getTeamDetail(teamId);
});

// 팀 멤버 목록 프로바이더 (팀 ID를 파라미터로 사용)
final teamMembersProvider =
    FutureProvider.family<List<TeamMember>, String>((ref, teamId) async {
  final api = ref.watch(teamApiProvider);
  return api.getMembers(teamId);
});
