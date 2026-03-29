// 미팅 목록 상태 관리 프로바이더 - SharedPreferences로 앱 재시작 시 데이터 유지
// @MX:ANCHOR: meetingListProvider는 홈/처리/결과 화면 모두에서 사용하는 핵심 상태
// @MX:REASON: 3개 이상 화면에서 참조되며, AsyncNotifier로 타입 변경 시 소비자 전체 수정 필요
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/services/history_api.dart';

// SharedPreferences 저장 키
const _kMeetingsKey = 'meetings_list';

// 미팅 목록 AsyncNotifier - 앱 재시작 시 SharedPreferences에서 복원
class MeetingListNotifier extends AsyncNotifier<List<Meeting>> {
  @override
  Future<List<Meeting>> build() async {
    // 앱 시작 시 로컬 저장소에서 미팅 목록 불러오기
    final prefs = await SharedPreferences.getInstance();
    final json = prefs.getString(_kMeetingsKey);
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
    await prefs.setString(_kMeetingsKey, json);
  }

  // 미팅 추가
  Future<void> addMeeting(Meeting meeting) async {
    final current = state.value ?? [];
    final updated = [...current, meeting];
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

  // 미팅 삭제 (로컬에서만 제거)
  Future<void> removeMeeting(String id) async {
    final current = state.value ?? [];
    final newList = current.where((m) => m.id != id).toList();
    state = AsyncData(newList);
    await _save(newList);
  }

  // @MX:NOTE: SPEC-HISTSYNC-001 REQ-HSYNC-002/003 - 서버 이력 동기화
  // 서버에서 summary 완료 이력을 가져와 로컬 목록과 병합 (중복 제외)
  // 오류 발생 시 로컬 데이터 보존 (REQ-HSYNC-007)
  Future<void> refreshFromServer() async {
    final historyApi = ref.read(historyApiProvider);
    try {
      final response = await historyApi.list(
        taskType: 'summary',
        status: 'completed',
      );
      final items = response['items'] as List<dynamic>;
      final current = state.value ?? [];
      final existingIds = current.map((m) => m.id).toSet();

      // 로컬에 없는 서버 항목만 변환하여 추가
      final newMeetings = items
          .cast<Map<String, dynamic>>()
          .where((item) => !existingIds.contains(item['task_id'] as String))
          .map(_historyItemToMeeting)
          .toList();

      if (newMeetings.isNotEmpty) {
        final merged = [...current, ...newMeetings];
        // 날짜 기준 최신순 정렬
        merged.sort((a, b) => b.createdAt.compareTo(a.createdAt));
        state = AsyncData(merged);
        await _save(merged);
      }
    } catch (_) {
      // 서버 오류 시 로컬 데이터 유지 (REQ-HSYNC-007)
      // 예외를 rethrow해서 홈 화면이 try-catch로 SnackBar 표시
      rethrow;
    }
  }

  // 서버 HistoryItem 맵을 Meeting 객체로 변환
  // summary task_id를 미팅 id 및 summaryTaskId로 사용
  Meeting _historyItemToMeeting(Map<String, dynamic> item) {
    final taskId = item['task_id'] as String;
    final createdAtStr = item['created_at'] as String;
    return Meeting(
      id: taskId,
      title: '미팅 (${_formatDateLabel(DateTime.parse(createdAtStr))})',
      createdAt: DateTime.parse(createdAtStr),
      status: MeetingStatus.completed,
      summaryTaskId: taskId,
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
