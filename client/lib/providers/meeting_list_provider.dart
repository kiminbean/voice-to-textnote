// 미팅 목록 상태 관리 프로바이더
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/meeting.dart';

// 미팅 목록 Notifier
class MeetingListNotifier extends Notifier<List<Meeting>> {
  @override
  List<Meeting> build() {
    return [];
  }

  // 미팅 추가
  void addMeeting(Meeting meeting) {
    state = [...state, meeting];
  }

  // 미팅 업데이트
  void updateMeeting(String id, Meeting updated) {
    state = state.map((m) => m.id == id ? updated : m).toList();
  }

  // 미팅 삭제
  void removeMeeting(String id) {
    state = state.where((m) => m.id != id).toList();
  }
}

// 미팅 목록 프로바이더
final meetingListProvider = NotifierProvider<MeetingListNotifier, List<Meeting>>(
  MeetingListNotifier.new,
);
