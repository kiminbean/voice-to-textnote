// MeetingListProvider 상태 관리 테스트 (AsyncNotifier 기반)
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';

void main() {
  group('MeetingListProvider', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
    });

    // 미팅 추가 테스트
    test('addMeeting이 미팅을 목록에 추가해야 함', () async {
      final meeting = Meeting(
        id: 'test-001',
        title: '테스트 미팅',
        createdAt: DateTime.now(),
        status: MeetingStatus.completed,
      );

      // AsyncNotifier가 초기화될 때까지 대기
      await container.read(meetingListProvider.future);

      await container.read(meetingListProvider.notifier).addMeeting(meeting);
      // AsyncValue에서 .value로 실제 목록 추출
      final meetings = container.read(meetingListProvider).value ?? [];

      expect(meetings.length, 1);
      expect(meetings.first.id, 'test-001');
    });

    // 미팅 업데이트 테스트
    test('updateMeeting이 미팅 정보를 올바르게 업데이트해야 함', () async {
      // 먼저 추가
      final original = Meeting(
        id: 'test-002',
        title: '원본 미팅',
        createdAt: DateTime.now(),
        status: MeetingStatus.processing,
      );

      await container.read(meetingListProvider.future);
      await container.read(meetingListProvider.notifier).addMeeting(original);

      // 업데이트
      final updated = original.copyWith(status: MeetingStatus.completed);
      await container
          .read(meetingListProvider.notifier)
          .updateMeeting('test-002', updated);

      final meetings = container.read(meetingListProvider).value ?? [];
      expect(meetings.first.status, MeetingStatus.completed);
    });

    // 미팅 삭제 테스트
    test('removeMeeting이 미팅을 목록에서 제거해야 함', () async {
      final meeting = Meeting(
        id: 'test-003',
        title: '삭제할 미팅',
        createdAt: DateTime.now(),
        status: MeetingStatus.completed,
      );

      await container.read(meetingListProvider.future);
      await container.read(meetingListProvider.notifier).addMeeting(meeting);
      await container
          .read(meetingListProvider.notifier)
          .removeMeeting('test-003');

      final meetings = container.read(meetingListProvider).value ?? [];
      expect(meetings.isEmpty, isTrue);
    });

    // 초기 상태 테스트
    test('초기 상태는 빈 목록이어야 함', () async {
      await container.read(meetingListProvider.future);
      final meetings = container.read(meetingListProvider).value ?? [];
      expect(meetings, isEmpty);
    });

    // 다중 미팅 관리 테스트
    test('여러 미팅을 추가하고 관리할 수 있어야 함', () async {
      await container.read(meetingListProvider.future);
      for (var i = 0; i < 3; i++) {
        await container.read(meetingListProvider.notifier).addMeeting(Meeting(
              id: 'test-$i',
              title: '미팅 $i',
              createdAt: DateTime.now(),
              status: MeetingStatus.completed,
            ));
      }

      final meetings = container.read(meetingListProvider).value ?? [];
      expect(meetings.length, 3);
    });
  });
}
