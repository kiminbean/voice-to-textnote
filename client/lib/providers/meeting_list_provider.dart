// 미팅 목록 상태 관리 프로바이더 - SharedPreferences로 앱 재시작 시 데이터 유지
// @MX:ANCHOR: meetingListProvider는 홈/처리/결과 화면 모두에서 사용하는 핵심 상태
// @MX:REASON: 3개 이상 화면에서 참조되며, AsyncNotifier로 타입 변경 시 소비자 전체 수정 필요
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/models/meeting.dart';

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

  // 미팅 삭제
  Future<void> removeMeeting(String id) async {
    final current = state.value ?? [];
    final newList = current.where((m) => m.id != id).toList();
    state = AsyncData(newList);
    await _save(newList);
  }
}

// 미팅 목록 프로바이더 (AsyncNotifier)
// @MX:NOTE: Notifier → AsyncNotifier로 변경 (SharedPreferences 비동기 로드 필요)
// @MX:NOTE: 소비자는 ref.watch(meetingListProvider) 대신 AsyncValue 처리 필요
final meetingListProvider =
    AsyncNotifierProvider<MeetingListNotifier, List<Meeting>>(
  MeetingListNotifier.new,
);
