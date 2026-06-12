// M3 단위 테스트: CollabMinutesNotifier 상태 관리
// SPEC-COLLAB-001: AC-030 ~ AC-034
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/providers/collab_minutes_provider.dart';
import 'package:voice_to_textnote/services/collab_socket_service.dart';

/// 테스트용 CollabSocketService 목
class MockCollabSocketService extends CollabSocketService {
  bool connectCalled = false;
  String? lastEditField;
  String? lastEditValue;
  String? lastCursorField;
  bool pingSent = false;

  final _controller = StreamController<CollabMessage>.broadcast();

  /// 목 서비스에 메시지 주입 (테스트에서 서버 응답 시뮬레이션)
  void injectMessage(CollabMessage msg) => _controller.add(msg);

  @override
  Stream<CollabMessage> get messages => _controller.stream;

  @override
  bool isConnected = false;

  @override
  Future<void> connect(String taskId, String token) async {
    connectCalled = true;
    isConnected = true;
  }

  @override
  void sendEdit(String field, String value) {
    lastEditField = field;
    lastEditValue = value;
  }

  @override
  void sendCursor(String? field) {
    lastCursorField = field;
  }

  @override
  void sendPing() {
    pingSent = true;
  }

  @override
  void disconnect() {
    isConnected = false;
  }

  @override
  void dispose() {
    _controller.close();
  }
}

void main() {
  late MockCollabSocketService mockSocket;
  late CollabMinutesNotifier notifier;

  setUp(() {
    mockSocket = MockCollabSocketService();
    notifier = CollabMinutesNotifier(mockSocket);
  });

  tearDown(() {
    notifier.dispose();
  });

  // AC-030: WebSocket 연결 수립
  test('AC-030: connect → isConnected가 true가 된다', () async {
    expect(notifier.state.isConnected, isFalse);

    await notifier.connect('task-001', 'jwt-token');

    expect(mockSocket.connectCalled, isTrue);
    expect(notifier.state.isConnected, isTrue);
    expect(notifier.state.error, isNull);
  });

  // AC-030: 연결 실패 시 error 상태
  test('AC-030: connect 실패 → error 상태', () async {
    // connect가 예외를 던지도록 설정
    final failSocket = _FailSocketService();
    final failNotifier = CollabMinutesNotifier(failSocket);

    await failNotifier.connect('task-001', 'bad-token');

    expect(failNotifier.state.isConnected, isFalse);
    expect(failNotifier.state.error, isNotNull);
    failNotifier.dispose();
  });

  // AC-032: 로컬 편집 전송
  test('AC-032: editField → WebSocket으로 edit 메시지 전송', () async {
    await notifier.connect('task-001', 'jwt-token');

    notifier.editField('summary_text', '새 내용');

    expect(mockSocket.lastEditField, 'summary_text');
    expect(mockSocket.lastEditValue, '새 내용');
  });

  // AC-032: 연결 안 된 상태에서 editField 호출 → 무시
  test('AC-032: disconnected 상태에서 editField → 무시', () {
    notifier.editField('summary_text', '무시됨');

    expect(mockSocket.lastEditField, isNull);
    expect(mockSocket.lastEditValue, isNull);
  });

  // AC-033: 원격 편집 수신 시 상태 갱신
  test('AC-033: edit_broadcast 수신 → fields 갱신', () async {
    await notifier.connect('task-001', 'jwt-token');

    mockSocket.injectMessage(CollabMessage(
      type: CollabMessageType.editBroadcast,
      raw: {
        'type': 'edit_broadcast',
        'field': 'action_items',
        'value': '새 액션 아이템',
        'user_id': 'user-b',
        'user_name': 'Bob',
        'server_ts': 1.0,
      },
    ));

    // StreamController broadcast → 약간의 대기
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(notifier.state.fields['action_items'], '새 액션 아이템');
  });

  // AC-033: sync_state 수신 시 전체 상태 갱신
  test('AC-033: sync_state 수신 → 전체 fields + activeUsers 갱신', () async {
    await notifier.connect('task-001', 'jwt-token');

    mockSocket.injectMessage(CollabMessage(
      type: CollabMessageType.syncState,
      raw: {
        'type': 'sync_state',
        'fields': {
          'summary_text': {'value': '수정된 요약', 'user_id': 'user-a', 'server_ts': 1.0},
          'action_items': {'value': '액션', 'user_id': 'user-b', 'server_ts': 2.0},
        },
        'active_users': [
          {'user_id': 'user-a', 'display_name': 'Alice', 'color': '#F00'},
          {'user_id': 'user-b', 'display_name': 'Bob', 'color': '#0F0'},
        ],
      },
    ));

    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(notifier.state.fields['summary_text'], '수정된 요약');
    expect(notifier.state.fields['action_items'], '액션');
    expect(notifier.state.activeUsers.length, 2);
    expect(notifier.state.activeUsers[0].userId, 'user-a');
  });

  // AC-033: user_joined 수신
  test('AC-033: user_joined 수신 → activeUsers에 추가', () async {
    await notifier.connect('task-001', 'jwt-token');

    mockSocket.injectMessage(CollabMessage(
      type: CollabMessageType.userJoined,
      raw: {
        'type': 'user_joined',
        'user_id': 'user-c',
        'display_name': 'Charlie',
        'color': '#00F',
      },
    ));

    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(notifier.state.activeUsers.any((u) => u.userId == 'user-c'), isTrue);
  });

  // AC-033: user_left 수신
  test('AC-033: user_left 수신 → activeUsers에서 제거', () async {
    await notifier.connect('task-001', 'jwt-token');

    // 먼저 user 추가
    mockSocket.injectMessage(CollabMessage(
      type: CollabMessageType.userJoined,
      raw: {'type': 'user_joined', 'user_id': 'user-c', 'display_name': 'C', 'color': '#00F'},
    ));
    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(notifier.state.activeUsers.any((u) => u.userId == 'user-c'), isTrue);

    // user 제거
    mockSocket.injectMessage(CollabMessage(
      type: CollabMessageType.userLeft,
      raw: {'type': 'user_left', 'user_id': 'user-c'},
    ));
    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(notifier.state.activeUsers.any((u) => u.userId == 'user-c'), isFalse);
  });

  // AC-034: startEditing → editingUsers에 'me' 추가
  test('AC-034: startEditing → editingUsers에 필드 등록', () async {
    await notifier.connect('task-001', 'jwt-token');

    notifier.startEditing('summary_text');

    expect(notifier.state.editingUsers['summary_text'], 'me');
  });

  // AC-034: stopEditing → editingUsers에서 'me' 제거
  test('AC-034: stopEditing → editingUsers에서 me 제거', () async {
    await notifier.connect('task-001', 'jwt-token');

    notifier.startEditing('summary_text');
    expect(notifier.state.editingUsers['summary_text'], 'me');

    notifier.stopEditing();
    expect(notifier.state.editingUsers.containsKey('summary_text'), isFalse);
  });

  // AC-034: 편집 중인 필드에 원격 edit_broadcast 수신 → 덮어쓰기 (LWW)
  // NOTE: 현재 구현에서는 editingUsers['me']와 무관하게 항상 fields 갱신.
  // UI 레이어(M4)에서 포커스 여부에 따라 무시/적용 분기.
  test('AC-034: 원격 edit_broadcast → fields 갱신 (LWW는 UI에서 분기)', () async {
    await notifier.connect('task-001', 'jwt-token');

    notifier.startEditing('summary_text');
    notifier.editField('summary_text', '내 편집');

    mockSocket.injectMessage(CollabMessage(
      type: CollabMessageType.editBroadcast,
      raw: {
        'type': 'edit_broadcast',
        'field': 'summary_text',
        'value': '상대방 편집',
        'user_id': 'user-b',
        'user_name': 'Bob',
        'server_ts': 99.0,
      },
    ));

    await Future<void>.delayed(const Duration(milliseconds: 50));

    // provider 레이어에서는 항상 갱신 (UI에서 포커스 분기)
    expect(notifier.state.fields['summary_text'], '상대방 편집');
  });

  // disconnect → 상태 초기화
  test('disconnect → 상태 초기화', () async {
    await notifier.connect('task-001', 'jwt-token');
    expect(notifier.state.isConnected, isTrue);

    notifier.disconnect();

    expect(notifier.state.isConnected, isFalse);
    expect(notifier.state.fields, isEmpty);
    expect(notifier.state.activeUsers, isEmpty);
  });

  // error 메시지 수신
  test('error 메시지 수신 → error 상태 설정', () async {
    await notifier.connect('task-001', 'jwt-token');

    mockSocket.injectMessage(CollabMessage(
      type: CollabMessageType.error,
      raw: {'type': 'error', 'code': 4005, 'message': '편집 권한 없음'},
    ));

    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(notifier.state.error, '편집 권한 없음');
  });

  // rate_limited 메시지 수신
  test('rate_limited 메시지 수신 → error 상태', () async {
    await notifier.connect('task-001', 'jwt-token');

    mockSocket.injectMessage(CollabMessage(
      type: CollabMessageType.rateLimited,
      raw: {'type': 'rate_limited', 'retry_after_ms': 1000},
    ));

    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(notifier.state.error, isNotNull);
    expect(notifier.state.error, contains('편집 속도'));
  });
}

/// 연결 실패 목 서비스
class _FailSocketService extends CollabSocketService {
  @override
  Stream<CollabMessage> get messages => const Stream.empty();

  @override
  bool isConnected = false;

  @override
  Future<void> connect(String taskId, String token) async {
    throw Exception('연결 실패');
  }

  @override
  void sendEdit(String field, String value) {}

  @override
  void sendCursor(String? field) {}

  @override
  void sendPing() {}

  @override
  void disconnect() {}

  @override
  void dispose() {}
}
