// 팀 API 서비스 (SPEC-TEAM-001 REQ-TEAM-006)
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/services/api_client.dart';

// TeamApi 프로바이더
// @MX:ANCHOR: 팀 CRUD 및 멤버 관리 API의 단일 진입점
// @MX:REASON: team_provider, team_list_screen, team_detail_screen에서 참조됨
final teamApiProvider = Provider<TeamApi>((ref) {
  final dio = ref.watch(dioProvider);
  return TeamApi(dio);
});

// 팀 관련 모든 API 호출을 담당하는 서비스 클래스
class TeamApi {
  final Dio _dio;

  TeamApi(this._dio);

  // === 팀 CRUD ===

  // 팀 생성
  // body: {name, description}
  Future<Team> createTeam({
    required String name,
    String? description,
  }) async {
    final response = await _dio.post('/teams', data: {
      'name': name,
      if (description != null) 'description': description,
    });
    return Team.fromJson(response.data as Map<String, dynamic>);
  }

  // 내가 속한 팀 목록 조회
  // returns: {items: [TeamResponse], total: int}
  Future<List<Team>> getTeams() async {
    final response = await _dio.get('/teams');
    final data = response.data as Map<String, dynamic>;
    final items = data['items'] as List<dynamic>;
    return items
        .map((item) => Team.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  // 팀 상세 조회 (멤버 목록 포함)
  Future<TeamDetail> getTeamDetail(String teamId) async {
    final response = await _dio.get('/teams/$teamId');
    return TeamDetail.fromJson(response.data as Map<String, dynamic>);
  }

  // 팀 정보 수정
  // body: {name?, description?}
  Future<Team> updateTeam(
    String teamId, {
    String? name,
    String? description,
  }) async {
    final response = await _dio.put('/teams/$teamId', data: {
      if (name != null) 'name': name,
      if (description != null) 'description': description,
    });
    return Team.fromJson(response.data as Map<String, dynamic>);
  }

  // 팀 삭제
  Future<void> deleteTeam(String teamId) async {
    await _dio.delete('/teams/$teamId');
  }

  // === 멤버 관리 ===

  // 멤버 초대
  // body: {email, role}
  Future<TeamMember> inviteMember(
    String teamId, {
    required String email,
    required String role,
  }) async {
    final response = await _dio.post('/teams/$teamId/members', data: {
      'email': email,
      'role': role,
    });
    return TeamMember.fromJson(response.data as Map<String, dynamic>);
  }

  // 멤버 목록 조회
  Future<List<TeamMember>> getMembers(String teamId) async {
    final response = await _dio.get('/teams/$teamId/members');
    final data = response.data as Map<String, dynamic>;
    final items = data['items'] as List<dynamic>;
    return items
        .map((item) => TeamMember.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  // 멤버 역할 변경
  // body: {role}
  Future<TeamMember> updateMemberRole(
    String teamId,
    String userId, {
    required String role,
  }) async {
    final response = await _dio.put(
      '/teams/$teamId/members/$userId',
      data: {'role': role},
    );
    return TeamMember.fromJson(response.data as Map<String, dynamic>);
  }

  // 멤버 제거 (자기 자신 나가기 포함)
  Future<void> removeMember(String teamId, String userId) async {
    await _dio.delete('/teams/$teamId/members/$userId');
  }

  // === 미팅 공유 ===

  // 미팅을 팀에 공유
  // body: {team_id}
  Future<MeetingShareResponse> shareMeeting(
    String taskId,
    String teamId,
  ) async {
    final response = await _dio.post('/meetings/$taskId/share', data: {
      'team_id': teamId,
    });
    return MeetingShareResponse.fromJson(response.data as Map<String, dynamic>);
  }

  // 미팅 공유 해제
  Future<void> unshareMeeting(String taskId, String teamId) async {
    await _dio.delete('/meetings/$taskId/share/$teamId');
  }

  // 팀에 공유된 미팅 목록 조회
  Future<List<Map<String, dynamic>>> getTeamMeetings(
    String teamId, {
    int page = 1,
    int pageSize = 20,
  }) async {
    final response = await _dio.get(
      '/teams/$teamId/meetings',
      queryParameters: {
        'page': page,
        'page_size': pageSize,
      },
    );
    final data = response.data as Map<String, dynamic>;
    return (data['items'] as List<dynamic>)
        .map((item) => item as Map<String, dynamic>)
        .toList();
  }
}
