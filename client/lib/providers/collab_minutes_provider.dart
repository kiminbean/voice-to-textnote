// 협업 편집 상태 관리 Riverpod Provider
// SPEC-COLLAB-001: REQ-COLLAB-031~034
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/collab_socket_service.dart';

/// 협업 편집 상태
class CollabMinutesState {
  final bool isConnected;
  final Map<String, String> fields;
  final List<CollabUser> activeUsers;
  final Map<String, String> editingUsers; // field → userId
  final String? error;

  const CollabMinutesState({
    this.isConnected = false,
    this.fields = const {},
    this.activeUsers = const [],
    this.editingUsers = const {},
    this.error,
  });

  CollabMinutesState copyWith({
    bool? isConnected,
    Map<String, String>? fields,
    List<CollabUser>? activeUsers,
    Map<String, String>? editingUsers,
    String? error,
  }) =>
      CollabMinutesState(
        isConnected: isConnected ?? this.isConnected,
        fields: fields ?? this.fields,
        activeUsers: activeUsers ?? this.activeUsers,
        editingUsers: editingUsers ?? this.editingUsers,
        error: error,
      );
}

/// 협업 편집 Notifier
class CollabMinutesNotifier extends StateNotifier<CollabMinutesState> {
  final CollabSocketService _socketService;
  StreamSubscription? _subscription;

  CollabMinutesNotifier(this._socketService)
      : super(const CollabMinutesState());

  /// WebSocket 연결 (REQ-COLLAB-030)
  Future<void> connect(String taskId, String token) async {
    try {
      await _socketService.connect(taskId, token);
      state = state.copyWith(isConnected: true, error: null);

      _subscription = _socketService.messages.listen(_handleMessage);
    } catch (e) {
      state = state.copyWith(
        isConnected: false,
        error: '연결 실패: $e',
      );
    }
  }

  /// 필드 편집 전송 (REQ-COLLAB-031)
  void editField(String field, String value) {
    if (!state.isConnected) return;
    _socketService.sendEdit(field, value);
  }

  /// 편집 시작 알림 (REQ-COLLAB-043)
  void startEditing(String field) {
    if (!state.isConnected) return;
    _socketService.sendCursor(field);
    state = state.copyWith(
      editingUsers: {...state.editingUsers, field: 'me'},
    );
  }

  /// 편집 종료 알림
  void stopEditing() {
    if (!state.isConnected) return;
    _socketService.sendCursor(null);
    final cleaned = Map<String, String>.from(state.editingUsers)
      ..removeWhere((k, v) => v == 'me');
    state = state.copyWith(editingUsers: cleaned);
  }

  /// 연결 해제
  void disconnect() {
    _subscription?.cancel();
    _subscription = null;
    _socketService.disconnect();
    state = const CollabMinutesState();
  }

  void _handleMessage(CollabMessage msg) {
    switch (msg.type) {
      case CollabMessageType.syncState:
        // REQ-COLLAB-032: 초기 상태 동기화
        final fields = <String, String>{};
        msg.fields.forEach((k, v) => fields[k] = v.value);
        state = state.copyWith(
          fields: fields,
          activeUsers: msg.activeUsers,
        );

      case CollabMessageType.editBroadcast:
        // REQ-COLLAB-031: 다른 사용자 편집 수신
        state = state.copyWith(
          fields: {...state.fields, msg.field: msg.value},
        );

      case CollabMessageType.userJoined:
        // REQ-COLLAB-033: 사용자 입장
        if (!state.activeUsers.any((u) => u.userId == msg.userId)) {
          state = state.copyWith(
            activeUsers: [
              ...state.activeUsers,
              CollabUser(
                userId: msg.userId,
                displayName: msg.userName,
                color: msg.raw['color'] as String? ?? '',
              ),
            ],
          );
        }

      case CollabMessageType.userLeft:
        // REQ-COLLAB-033: 사용자 퇴장
        state = state.copyWith(
          activeUsers: state.activeUsers
              .where((u) => u.userId != msg.userId)
              .toList(),
        );

      case CollabMessageType.error:
        state = state.copyWith(
          error: msg.raw['message'] as String? ?? '알 수 없는 오류',
        );

      case CollabMessageType.rateLimited:
        state = state.copyWith(
          error: '편집 속도가 너무 빠릅니다. 잠시 후 다시 시도하세요.',
        );
    }
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _socketService.dispose();
    super.dispose();
  }
}

/// CollabSocketService 프로바이더
final collabSocketServiceProvider = Provider<CollabSocketService>((ref) {
  return CollabSocketService();
});

/// 협업 편집 상태 프로바이더
final collabMinutesProvider =
    StateNotifierProvider<CollabMinutesNotifier, CollabMinutesState>(
  (ref) {
    final socketService = ref.watch(collabSocketServiceProvider);
    return CollabMinutesNotifier(socketService);
  },
);
