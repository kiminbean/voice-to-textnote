// 미팅 목록 상태 관리 프로바이더 - SharedPreferences로 앱 재시작 시 데이터 유지
// @MX:ANCHOR: meetingListProvider는 홈/처리/결과 화면 모두에서 사용하는 핵심 상태
// @MX:REASON: 3개 이상 화면에서 참조되며, AsyncNotifier로 타입 변경 시 소비자 전체 수정 필요
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:jwt_decoder/jwt_decoder.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/services/auth_service.dart';
import 'package:voice_to_textnote/services/history_api.dart';

// SharedPreferences 저장 키
const _kMeetingsKey = 'meetings_list';
const _kMeetingsScopedPrefix = 'meetings_list_v2';

// 미팅 목록 AsyncNotifier - 앱 재시작 시 SharedPreferences에서 복원
class MeetingListNotifier extends AsyncNotifier<List<Meeting>> {
  @override
  Future<List<Meeting>> build() async {
    final localMeetings = await _loadLocal();
    try {
      return await _mergeServerMeetings(localMeetings);
    } catch (_) {
      return localMeetings;
    }
  }

  Future<List<Meeting>> _loadLocal() async {
    final prefs = await SharedPreferences.getInstance();
    final json = prefs.getString(await _storageKey());
    if (json != null) {
      try {
        final list = jsonDecode(json) as List;
        return list
            .map((e) => Meeting.fromJson(e as Map<String, dynamic>))
            .toList();
      } catch (_) {
        // 파싱 실패 시 빈 목록 반환 (손상된 데이터 무시)
        return [];
      }
    }
    return [];
  }

  // 변경된 목록을 SharedPreferences에 저장
  Future<void> _save(List<Meeting> meetings) async {
    final prefs = await SharedPreferences.getInstance();
    final json = jsonEncode(meetings.map((m) => m.toJson()).toList());
    await prefs.setString(await _storageKey(), json);
  }

  Future<String> _storageKey() async {
    final authService = ref.read(authServiceProvider);
    final accessToken = await authService.getAccessToken();
    if (accessToken != null && accessToken.isNotEmpty) {
      final userId = _jwtSubject(accessToken);
      return '$_kMeetingsScopedPrefix:user:${userId ?? accessToken}';
    }

    final guestSessionId = await authService.getGuestSessionId();
    if (guestSessionId != null && guestSessionId.isNotEmpty) {
      return '$_kMeetingsScopedPrefix:guest:$guestSessionId';
    }

    final guestToken = await authService.getGuestToken();
    if (guestToken != null && guestToken.isNotEmpty) {
      final guestId = _jwtSubject(guestToken);
      return '$_kMeetingsScopedPrefix:guest:${guestId ?? guestToken}';
    }

    return '$_kMeetingsScopedPrefix:anonymous';
  }

  String? _jwtSubject(String token) {
    try {
      final payload = JwtDecoder.decode(token);
      final subject = payload['sub'];
      return subject is String && subject.isNotEmpty ? subject : null;
    } catch (_) {
      return null;
    }
  }

  // 미팅 추가
  Future<void> addMeeting(Meeting meeting) async {
    final current = state.value ?? [];
    final updated = [
      ...current.where((item) => item.id != meeting.id),
      meeting,
    ];
    state = AsyncData(updated);
    await _save(updated);
  }

  // 미팅 업데이트
  Future<void> updateMeeting(String id, Meeting updated) async {
    final current = state.value ?? [];
    final newList = current.map((m) => m.id == id ? updated : m).toList();
    state = AsyncData(newList);
    await _save(newList);
  }

  // 신원 전환(로그인/로그아웃/게스트 시작) 시 호출: 이전 신원의 로컬 회의 캐시를 비운다.
  // 회의 목록은 SharedPreferences에 신원 구분 없이 전역 저장되므로, 신원이 바뀌면
  // 이전 사용자의 회의가 남아 목록에 노출되고(서버는 404) "불러올 수 없습니다"를 유발한다.
  // 캐시를 비운 뒤 현재 신원 기준으로 서버에서 다시 동기화한다.
  Future<void> clearLocalCache() async {
    final prefs = await SharedPreferences.getInstance();
    await Future.wait([
      prefs.remove(_kMeetingsKey),
      prefs.remove(await _storageKey()),
    ]);
    state = const AsyncData<List<Meeting>>([]);
  }

  // 미팅 삭제 (로컬에서만 제거)
  Future<void> removeMeeting(String id) async {
    final current = state.value ?? [];
    final newList = current.where((m) => m.id != id).toList();
    state = AsyncData(newList);
    await _save(newList);
  }

  // @MX:NOTE: SPEC-HISTSYNC-001 REQ-HSYNC-002/003 - 서버 이력 동기화
  // 서버에서 summary/minutes 완료 이력을 가져와 로컬 목록과 병합 (중복 제외)
  // 오류 발생 시 로컬 데이터 보존 (REQ-HSYNC-007)
  Future<void> refreshFromServer() async {
    try {
      final current = state.value ?? [];
      final merged = await _mergeServerMeetings(current);
      state = AsyncData(merged);
    } catch (_) {
      // 서버 오류 시 로컬 데이터 유지 (REQ-HSYNC-007)
      // 예외를 rethrow해서 홈 화면이 try-catch로 SnackBar 표시
      rethrow;
    }
  }

  Future<List<Meeting>> _mergeServerMeetings(List<Meeting> current) async {
    final historyApi = ref.read(historyApiProvider);
    final summaryResponse = await historyApi.list(
      taskType: 'summary',
      status: 'completed',
    );
    final minutesResponse = await historyApi.list(
      taskType: 'minutes',
      status: 'completed',
    );
    final existingIds = current.map((m) => m.id).toSet();
    final serverMeetings = _dedupeServerMeetings([
      ..._historyItemsToMeetings(minutesResponse),
      ..._historyItemsToMeetings(summaryResponse),
    ]);

    final newMeetings =
        serverMeetings.where((meeting) => !existingIds.contains(meeting.id));

    final serverMeetingsById = {
      for (final meeting in serverMeetings) meeting.id: meeting,
    };
    final refreshedCurrent = current.map((meeting) {
      final serverMeeting = serverMeetingsById[meeting.id];
      if (serverMeeting == null) return meeting;
      return meeting.copyWith(
        sharedTeamIds: serverMeeting.sharedTeamIds,
        summaryTaskId: meeting.summaryTaskId ?? serverMeeting.summaryTaskId,
      );
    }).toList();

    final merged = [...refreshedCurrent, ...newMeetings];
    merged.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    await _save(merged);
    return merged;
  }

  List<Meeting> _historyItemsToMeetings(Map<String, dynamic> response) {
    final items = response['items'] as List<dynamic>;
    return items
        .cast<Map<String, dynamic>>()
        .map(_historyItemToMeeting)
        .toList();
  }

  List<Meeting> _dedupeServerMeetings(List<Meeting> meetings) {
    final byId = <String, Meeting>{};
    for (final meeting in meetings) {
      final existing = byId[meeting.id];
      if (existing == null) {
        byId[meeting.id] = meeting;
        continue;
      }
      byId[meeting.id] = existing.copyWith(
        title: meeting.summaryTaskId != null ? meeting.title : existing.title,
        createdAt: meeting.createdAt.isAfter(existing.createdAt)
            ? meeting.createdAt
            : existing.createdAt,
        minutesTaskId: existing.minutesTaskId ?? meeting.minutesTaskId,
        summaryTaskId: existing.summaryTaskId ?? meeting.summaryTaskId,
        sharedTeamIds: meeting.sharedTeamIds.isNotEmpty
            ? meeting.sharedTeamIds
            : existing.sharedTeamIds,
      );
    }
    return byId.values.toList();
  }

  // 서버 HistoryItem 맵을 Meeting 객체로 변환
  // summary는 source_task_id가 있으면 원본 minutes task_id를 미팅 id로 사용
  Meeting _historyItemToMeeting(Map<String, dynamic> item) {
    final taskId = item['task_id'] as String;
    final taskType = item['task_type'] as String?;
    final sourceTaskId = item['source_task_id'] as String?;
    final meetingId = taskType == 'summary' ? (sourceTaskId ?? taskId) : taskId;
    final createdAtStr = item['created_at'] as String;
    return Meeting(
      id: meetingId,
      title: '미팅 (${_formatDateLabel(DateTime.parse(createdAtStr))})',
      createdAt: DateTime.parse(createdAtStr),
      status: MeetingStatus.completed,
      minutesTaskId: taskType == 'minutes' ? taskId : sourceTaskId,
      summaryTaskId: taskType == 'summary' ? taskId : null,
      sharedTeamIds: (item['shared_team_ids'] as List<dynamic>?)
              ?.map((teamId) => teamId as String)
              .toList(growable: false) ??
          const [],
    );
  }

  // 날짜를 사람이 읽기 쉬운 레이블로 변환
  String _formatDateLabel(DateTime dt) {
    return '${dt.year}.${dt.month.toString().padLeft(2, '0')}.${dt.day.toString().padLeft(2, '0')}';
  }
}

// 미팅 목록 프로바이더 (AsyncNotifier)
// @MX:NOTE: Notifier → AsyncNotifier로 변경 (SharedPreferences 비동기 로드 필요)
// @MX:NOTE: 소비자는 ref.watch(meetingListProvider) 대신 AsyncValue 처리 필요
final meetingListProvider =
    AsyncNotifierProvider<MeetingListNotifier, List<Meeting>>(
  MeetingListNotifier.new,
);
