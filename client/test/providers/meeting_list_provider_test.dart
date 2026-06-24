// MeetingListProvider 상태 관리 테스트 (AsyncNotifier 기반)
// SPEC-HISTSYNC-001: 서버 동기화 로직 포함
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/services/auth_service.dart';
import 'package:voice_to_textnote/services/history_api.dart';

// HistoryApi Mock 클래스
class MockHistoryApi extends Mock implements HistoryApi {}

class FakeAuthService extends AuthService {
  FakeAuthService({
    this.accessToken,
    this.guestToken,
    this.guestSessionId,
  });

  final String? accessToken;
  final String? guestToken;
  final String? guestSessionId;

  @override
  Future<String?> getAccessToken() async => accessToken;

  @override
  Future<String?> getGuestToken() async => guestToken;

  @override
  Future<String?> getGuestSessionId() async => guestSessionId;
}

void main() {
  // SharedPreferences 바인딩 초기화
  TestWidgetsFlutterBinding.ensureInitialized();

  group('MeetingListProvider', () {
    late ProviderContainer container;
    late MockHistoryApi mockHistoryApi;

    setUp(() {
      // 테스트 환경에서 SharedPreferences 목 초기화
      SharedPreferences.setMockInitialValues({});
      mockHistoryApi = MockHistoryApi();
      when(() => mockHistoryApi.list(
            taskType: any(named: 'taskType'),
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [],
          'total': 0,
          'page': 1,
          'page_size': 20,
        },
      );
      container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(FakeAuthService()),
        ],
      );
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

  // SPEC-HISTSYNC-001: 서버 동기화 테스트 그룹
  group('MeetingListProvider - 서버 동기화 (SPEC-HISTSYNC-001)', () {
    late MockHistoryApi mockHistoryApi;

    setUp(() {
      // 각 테스트마다 SharedPreferences 초기화
      SharedPreferences.setMockInitialValues({});
      mockHistoryApi = MockHistoryApi();
    });

    // REQ-HSYNC-002: 서버 이력이 로컬 목록에 없는 경우 병합 테스트
    test('refreshFromServer가 서버 이력을 로컬 목록과 병합해야 함', () async {
      // Arrange: 서버에 1개의 summary 이력이 있음
      when(() => mockHistoryApi.list(
            taskType: any(named: 'taskType'),
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [
            {
              'task_id': 'srv-001',
              'task_type': 'summary',
              'status': 'completed',
              'created_at': '2024-01-15T10:00:00Z',
              'completed_at': '2024-01-15T10:05:00Z',
            }
          ],
          'total': 1,
          'page': 1,
          'page_size': 20,
        },
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(FakeAuthService()),
        ],
      );
      addTearDown(container.dispose);

      await container.read(meetingListProvider.future);

      // Act: 서버에서 새로 고침
      await container.read(meetingListProvider.notifier).refreshFromServer();

      // Assert: 서버 이력이 목록에 추가됨
      final meetings = container.read(meetingListProvider).value ?? [];
      expect(meetings.any((m) => m.id == 'srv-001'), isTrue);
    });

    test('초기 로드 시 서버 이력을 자동으로 병합해야 함', () async {
      when(() => mockHistoryApi.list(
            taskType: any(named: 'taskType'),
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [
            {
              'task_id': 'srv-auto-001',
              'task_type': 'summary',
              'status': 'completed',
              'created_at': '2024-01-15T10:00:00Z',
              'completed_at': '2024-01-15T10:05:00Z',
            }
          ],
          'total': 1,
          'page': 1,
          'page_size': 20,
        },
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(FakeAuthService()),
        ],
      );
      addTearDown(container.dispose);

      final meetings = await container.read(meetingListProvider.future);

      expect(meetings.any((m) => m.id == 'srv-auto-001'), isTrue);
      verify(() => mockHistoryApi.list(
            taskType: 'summary',
            status: 'completed',
            page: 1,
            pageSize: 20,
          )).called(1);
      verify(() => mockHistoryApi.list(
            taskType: 'minutes',
            status: 'completed',
            page: 1,
            pageSize: 20,
          )).called(1);
    });

    test('refreshFromServer가 summary가 없는 minutes 완료 이력도 복원해야 함', () async {
      when(() => mockHistoryApi.list(
            taskType: 'summary',
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [],
          'total': 0,
          'page': 1,
          'page_size': 20,
        },
      );
      when(() => mockHistoryApi.list(
            taskType: 'minutes',
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [
            {
              'task_id': 'min-restore-001',
              'task_type': 'minutes',
              'status': 'completed',
              'created_at': '2026-06-22T15:27:59Z',
              'completed_at': '2026-06-22T15:28:00Z',
            }
          ],
          'total': 1,
          'page': 1,
          'page_size': 20,
        },
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(FakeAuthService()),
        ],
      );
      addTearDown(container.dispose);

      await container.read(meetingListProvider.future);
      await container.read(meetingListProvider.notifier).refreshFromServer();

      final meetings = container.read(meetingListProvider).value ?? [];
      final meeting = meetings.firstWhere((m) => m.id == 'min-restore-001');
      expect(meeting.minutesTaskId, 'min-restore-001');
      expect(meeting.summaryTaskId, isNull);
    });

    test('refreshFromServer가 같은 회의의 minutes와 summary를 하나로 병합해야 함', () async {
      when(() => mockHistoryApi.list(
            taskType: 'minutes',
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [
            {
              'task_id': 'min-merge-001',
              'task_type': 'minutes',
              'status': 'completed',
              'created_at': '2026-06-22T15:27:59Z',
              'completed_at': '2026-06-22T15:28:00Z',
            }
          ],
          'total': 1,
          'page': 1,
          'page_size': 20,
        },
      );
      when(() => mockHistoryApi.list(
            taskType: 'summary',
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [
            {
              'task_id': 'sum-merge-001',
              'task_type': 'summary',
              'status': 'completed',
              'source_task_id': 'min-merge-001',
              'created_at': '2026-06-22T15:30:00Z',
              'completed_at': '2026-06-22T15:30:10Z',
              'shared_team_ids': ['team-001'],
            }
          ],
          'total': 1,
          'page': 1,
          'page_size': 20,
        },
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(FakeAuthService()),
        ],
      );
      addTearDown(container.dispose);

      await container.read(meetingListProvider.future);
      await container.read(meetingListProvider.notifier).refreshFromServer();

      final meetings = container.read(meetingListProvider).value ?? [];
      final merged = meetings.where((m) => m.id == 'min-merge-001').toList();
      expect(merged.length, 1);
      expect(merged.single.minutesTaskId, 'min-merge-001');
      expect(merged.single.summaryTaskId, 'sum-merge-001');
      expect(merged.single.sharedTeamIds, ['team-001']);
    });

    // REQ-HSYNC-002: 로컬에 이미 있는 이력은 중복 추가 안 함
    test('refreshFromServer가 이미 로컬에 있는 미팅은 중복 추가하지 않아야 함', () async {
      // Arrange: 서버와 로컬 모두 동일한 항목 보유
      when(() => mockHistoryApi.list(
            taskType: any(named: 'taskType'),
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [
            {
              'task_id': 'local-001',
              'task_type': 'summary',
              'status': 'completed',
              'created_at': '2024-01-15T10:00:00Z',
              'completed_at': '2024-01-15T10:05:00Z',
            }
          ],
          'total': 1,
          'page': 1,
          'page_size': 20,
        },
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(FakeAuthService()),
        ],
      );
      addTearDown(container.dispose);

      await container.read(meetingListProvider.future);

      // 로컬에 동일한 id 미팅 추가
      await container.read(meetingListProvider.notifier).addMeeting(Meeting(
            id: 'local-001',
            title: '기존 미팅',
            createdAt: DateTime(2024, 1, 15, 10, 0),
            status: MeetingStatus.completed,
          ));

      // Act
      await container.read(meetingListProvider.notifier).refreshFromServer();

      // Assert: 중복 없이 1개만 존재
      final meetings = container.read(meetingListProvider).value ?? [];
      final localItems = meetings.where((m) => m.id == 'local-001').toList();
      expect(localItems.length, 1);
    });

    // REQ-HSYNC-007: 서버 오류 시 로컬 데이터 보존 테스트
    test('refreshFromServer가 서버 오류 시 로컬 데이터를 보존해야 함', () async {
      // Arrange: 서버 호출 시 예외 발생
      when(() => mockHistoryApi.list(
            taskType: any(named: 'taskType'),
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          message: '서버 연결 오류',
        ),
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(FakeAuthService()),
        ],
      );
      addTearDown(container.dispose);

      await container.read(meetingListProvider.future);

      // 로컬에 1개 미팅 추가
      await container.read(meetingListProvider.notifier).addMeeting(Meeting(
            id: 'local-001',
            title: '로컬 미팅',
            createdAt: DateTime.now(),
            status: MeetingStatus.completed,
          ));

      // Act: 서버 오류 시 예외가 전파되어야 하고, 로컬 데이터는 유지되어야 함
      // 호출자(홈 화면)가 try-catch로 SnackBar 표시
      await expectLater(
        container.read(meetingListProvider.notifier).refreshFromServer(),
        throwsA(isA<Exception>()),
      );

      // Assert: 로컬 데이터 보존 (state는 변경되지 않음)
      final meetings = container.read(meetingListProvider).value ?? [];
      expect(meetings.length, 1);
      expect(meetings.first.id, 'local-001');
    });

    // REQ-HSYNC-002: 서버 이력에서 Meeting 객체 변환 테스트
    test('refreshFromServer가 서버 HistoryItem을 Meeting으로 올바르게 변환해야 함', () async {
      // Arrange
      when(() => mockHistoryApi.list(
            taskType: any(named: 'taskType'),
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [
            {
              'task_id': 'sum-abc',
              'task_type': 'summary',
              'status': 'completed',
              'created_at': '2024-03-01T09:00:00Z',
              'completed_at': '2024-03-01T09:10:00Z',
              'shared_team_ids': ['team-001', 'team-002'],
            }
          ],
          'total': 1,
          'page': 1,
          'page_size': 20,
        },
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(FakeAuthService()),
        ],
      );
      addTearDown(container.dispose);

      await container.read(meetingListProvider.future);

      // Act
      await container.read(meetingListProvider.notifier).refreshFromServer();

      // Assert: Meeting 변환 검증
      final meetings = container.read(meetingListProvider).value ?? [];
      final meeting = meetings.firstWhere((m) => m.id == 'sum-abc');
      expect(meeting.status, MeetingStatus.completed);
      expect(meeting.summaryTaskId, 'sum-abc');
      expect(meeting.createdAt, DateTime.utc(2024, 3, 1, 9, 0, 0));
      expect(meeting.sharedTeamIds, ['team-001', 'team-002']);
    });

    test('refreshFromServer가 기존 로컬 미팅의 공유 팀 상태를 갱신해야 함', () async {
      // Arrange
      when(() => mockHistoryApi.list(
            taskType: any(named: 'taskType'),
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [
            {
              'task_id': 'local-001',
              'task_type': 'summary',
              'status': 'completed',
              'created_at': '2024-03-01T09:00:00Z',
              'completed_at': '2024-03-01T09:10:00Z',
              'shared_team_ids': ['team-shared'],
            }
          ],
          'total': 1,
          'page': 1,
          'page_size': 20,
        },
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(FakeAuthService()),
        ],
      );
      addTearDown(container.dispose);

      await container.read(meetingListProvider.future);
      await container.read(meetingListProvider.notifier).addMeeting(Meeting(
            id: 'local-001',
            title: '기존 미팅',
            createdAt: DateTime(2024, 3, 1, 9),
            status: MeetingStatus.completed,
          ));

      // Act
      await container.read(meetingListProvider.notifier).refreshFromServer();

      // Assert
      final meetings = container.read(meetingListProvider).value ?? [];
      final meeting = meetings.firstWhere((m) => m.id == 'local-001');
      expect(meeting.sharedTeamIds, ['team-shared']);
      expect(meeting.title, '기존 미팅');
    });

    test('게스트 세션은 이전 전역 캐시의 로그인 회의를 로드하지 않아야 함', () async {
      final staleMeeting = Meeting(
        id: 'previous-user-meeting',
        title: '이전 로그인 회의',
        createdAt: DateTime(2026, 6, 24, 10),
        status: MeetingStatus.completed,
        minutesTaskId: 'previous-minutes',
        summaryTaskId: 'previous-summary',
      );
      SharedPreferences.setMockInitialValues({
        'meetings_list': jsonEncode([staleMeeting.toJson()]),
      });
      when(() => mockHistoryApi.list(
            taskType: any(named: 'taskType'),
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [],
          'total': 0,
          'page': 1,
          'page_size': 20,
        },
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(
            FakeAuthService(
              guestToken: 'guest-token',
              guestSessionId: 'guest-session-current',
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      final meetings = await container.read(meetingListProvider.future);

      expect(meetings, isEmpty);
    });

    test('회의 목록 캐시는 게스트 세션별로 분리되어야 함', () async {
      final otherGuestMeeting = Meeting(
        id: 'other-guest-meeting',
        title: '다른 게스트 회의',
        createdAt: DateTime(2026, 6, 24, 11),
        status: MeetingStatus.completed,
        minutesTaskId: 'other-minutes',
      );
      SharedPreferences.setMockInitialValues({
        'meetings_list_v2:guest:other-session':
            jsonEncode([otherGuestMeeting.toJson()]),
      });
      when(() => mockHistoryApi.list(
            taskType: any(named: 'taskType'),
            status: any(named: 'status'),
            page: any(named: 'page'),
            pageSize: any(named: 'pageSize'),
          )).thenAnswer(
        (_) async => {
          'items': [],
          'total': 0,
          'page': 1,
          'page_size': 20,
        },
      );

      final container = ProviderContainer(
        overrides: [
          historyApiProvider.overrideWithValue(mockHistoryApi),
          authServiceProvider.overrideWithValue(
            FakeAuthService(
              guestToken: 'guest-token',
              guestSessionId: 'current-session',
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      final meetings = await container.read(meetingListProvider.future);

      expect(meetings, isEmpty);
    });
  });
}
