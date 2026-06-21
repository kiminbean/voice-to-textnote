// Meeting 모델 테스트
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/meeting.dart';

void main() {
  group('Meeting 모델', () {
    // 기본 생성 테스트
    test('Meeting 기본 생성이 올바르게 동작해야 함', () {
      final now = DateTime.now();
      final meeting = Meeting(
        id: 'test-id-001',
        title: '주간 팀 미팅',
        createdAt: now,
        status: MeetingStatus.completed,
      );

      expect(meeting.id, 'test-id-001');
      expect(meeting.title, '주간 팀 미팅');
      expect(meeting.createdAt, now);
      expect(meeting.status, MeetingStatus.completed);
      expect(meeting.duration, isNull);
      expect(meeting.transcriptionTaskId, isNull);
      expect(meeting.diarizationTaskId, isNull);
      expect(meeting.minutesTaskId, isNull);
      expect(meeting.summaryTaskId, isNull);
      expect(meeting.sharedTeamIds, isEmpty);
    });

    // 선택적 필드 포함 생성 테스트
    test('Meeting 선택적 필드 포함 생성이 올바르게 동작해야 함', () {
      final meeting = Meeting(
        id: 'test-id-002',
        title: '기술 리뷰',
        createdAt: DateTime(2024, 1, 15),
        status: MeetingStatus.processing,
        duration: const Duration(minutes: 30),
        sourceUrl: 'https://meet.google.com/abc-defg-hij',
        transcriptionTaskId: 'stt-task-001',
        diarizationTaskId: 'dia-task-001',
        minutesTaskId: 'min-task-001',
        summaryTaskId: 'sum-task-001',
        vocabularyId: 'vocab-001',
        sharedTeamIds: const ['team-001'],
      );

      expect(meeting.duration, const Duration(minutes: 30));
      expect(meeting.sourceUrl, 'https://meet.google.com/abc-defg-hij');
      expect(meeting.transcriptionTaskId, 'stt-task-001');
      expect(meeting.diarizationTaskId, 'dia-task-001');
      expect(meeting.minutesTaskId, 'min-task-001');
      expect(meeting.summaryTaskId, 'sum-task-001');
      expect(meeting.vocabularyId, 'vocab-001');
      expect(meeting.sharedTeamIds, ['team-001']);
    });

    // copyWith 테스트
    test('copyWith가 올바르게 동작해야 함', () {
      final original = Meeting(
        id: 'test-id-003',
        title: '원본 미팅',
        createdAt: DateTime(2024, 1, 1),
        status: MeetingStatus.recording,
      );

      final updated = original.copyWith(
        status: MeetingStatus.completed,
        sourceUrl: 'https://teams.microsoft.com/l/meetup-join/example',
        transcriptionTaskId: 'stt-task-002',
        sharedTeamIds: const ['team-002'],
      );

      // 변경된 필드 확인
      expect(updated.status, MeetingStatus.completed);
      expect(updated.sourceUrl,
          'https://teams.microsoft.com/l/meetup-join/example');
      expect(updated.transcriptionTaskId, 'stt-task-002');
      expect(updated.sharedTeamIds, ['team-002']);

      // 변경되지 않은 필드 확인
      expect(updated.id, original.id);
      expect(updated.title, original.title);
      expect(updated.createdAt, original.createdAt);
    });

    // JSON 직렬화 테스트
    test('fromJson이 올바르게 동작해야 함', () {
      final json = {
        'id': 'test-id-004',
        'title': 'JSON 테스트 미팅',
        'createdAt': '2024-01-15T10:00:00.000Z',
        'status': 'completed',
        'duration': 1800000, // 30분 (밀리초)
        'sourceUrl': 'https://meet.google.com/abc-defg-hij',
        'transcriptionTaskId': 'stt-001',
        'diarizationTaskId': null,
        'minutesTaskId': null,
        'summaryTaskId': null,
        'vocabularyId': 'vocab-002',
        'sharedTeamIds': ['team-003', 'team-004'],
      };

      final meeting = Meeting.fromJson(json);

      expect(meeting.id, 'test-id-004');
      expect(meeting.title, 'JSON 테스트 미팅');
      expect(meeting.status, MeetingStatus.completed);
      expect(meeting.duration, const Duration(milliseconds: 1800000));
      expect(meeting.sourceUrl, 'https://meet.google.com/abc-defg-hij');
      expect(meeting.transcriptionTaskId, 'stt-001');
      expect(meeting.vocabularyId, 'vocab-002');
      expect(meeting.sharedTeamIds, ['team-003', 'team-004']);
    });

    test('fromJson은 sharedTeamIds가 없으면 비공개 기본값을 사용해야 함', () {
      final meeting = Meeting.fromJson({
        'id': 'private-001',
        'title': '비공개 미팅',
        'createdAt': '2024-01-15T10:00:00.000Z',
        'status': 'completed',
      });

      expect(meeting.sharedTeamIds, isEmpty);
    });

    // JSON 역직렬화 테스트
    test('toJson이 올바르게 동작해야 함', () {
      final createdAt = DateTime(2024, 1, 15, 10, 0, 0);
      final meeting = Meeting(
        id: 'test-id-005',
        title: 'toJson 테스트',
        createdAt: createdAt,
        status: MeetingStatus.failed,
        duration: const Duration(minutes: 45),
        sourceUrl: 'https://zoom.us/j/123456789',
        vocabularyId: 'vocab-003',
        sharedTeamIds: const ['team-005'],
      );

      final json = meeting.toJson();

      expect(json['id'], 'test-id-005');
      expect(json['title'], 'toJson 테스트');
      expect(json['status'], 'failed');
      expect(json['duration'], 2700000); // 45분 (밀리초)
      expect(json['sourceUrl'], 'https://zoom.us/j/123456789');
      expect(json['vocabularyId'], 'vocab-003');
      expect(json['sharedTeamIds'], ['team-005']);
    });

    // MeetingStatus 열거형 테스트
    test('모든 MeetingStatus 값이 존재해야 함', () {
      expect(
          MeetingStatus.values,
          containsAll([
            MeetingStatus.recording,
            MeetingStatus.scheduled,
            MeetingStatus.processing,
            MeetingStatus.completed,
            MeetingStatus.failed,
          ]));
    });
  });
}
