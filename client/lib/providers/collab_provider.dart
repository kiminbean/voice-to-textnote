// SPEC-COLLAB-001: 실시간 공동 편집 상태 관리 프로바이더
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/collab_service.dart';

final collabProvider =
    StateNotifierProvider.autoDispose<CollabNotifier, CollabState>(
  (ref) => CollabNotifier(ref.watch(collabServiceProvider)),
);

class CollabState {
  final CollabConnectionState connectionState;
  final Map<String, dynamic> document;
  final Map<String, DateTime> fieldTimestamps;
  final List<PresenceUser> presence;
  final String? errorMessage;

  const CollabState({
    required this.connectionState,
    required this.document,
    required this.fieldTimestamps,
    required this.presence,
    this.errorMessage,
  });

  factory CollabState.initial() => const CollabState(
        connectionState: CollabConnectionState.disconnected,
        document: {},
        fieldTimestamps: {},
        presence: [],
      );

  CollabState copyWith({
    CollabConnectionState? connectionState,
    Map<String, dynamic>? document,
    Map<String, DateTime>? fieldTimestamps,
    List<PresenceUser>? presence,
    String? errorMessage,
  }) {
    return CollabState(
      connectionState: connectionState ?? this.connectionState,
      document: document ?? this.document,
      fieldTimestamps: fieldTimestamps ?? this.fieldTimestamps,
      presence: presence ?? this.presence,
      errorMessage: errorMessage,
    );
  }
}

class CollabNotifier extends StateNotifier<CollabState> {
  final CollabService _service;
  StreamSubscription? _connSub;
  StreamSubscription? _snapSub;
  StreamSubscription? _editSub;
  StreamSubscription? _presenceSub;
  StreamSubscription? _errorSub;

  CollabNotifier(this._service) : super(CollabState.initial()) {
    _connSub = _service.onConnectionChange.listen((s) {
      state = state.copyWith(connectionState: s);
    });
    _snapSub = _service.onSnapshot.listen((snap) {
      state = state.copyWith(
        document: Map.from(snap.document),
        fieldTimestamps: Map.from(snap.fieldTimestamps),
        presence: List.from(snap.presence),
      );
    });
    _editSub = _service.onEdit.listen((edit) {
      if (!edit.applied) return;
      final doc = Map<String, dynamic>.from(state.document);
      doc[edit.field] = edit.value;
      final ts = Map<String, DateTime>.from(state.fieldTimestamps);
      ts[edit.field] = edit.serverTimestamp;
      state = state.copyWith(document: doc, fieldTimestamps: ts);
    });
    _presenceSub = _service.onPresenceChange.listen((list) {
      state = state.copyWith(presence: List.from(list));
    });
    _errorSub = _service.onError.listen((msg) {
      state = state.copyWith(errorMessage: msg);
    });
  }

  Future<void> connect(String taskId) => _service.connect(taskId);

  void sendEdit(String field, dynamic value) => _service.sendEdit(field, value);

  void sendCursor(String field) => _service.sendCursor(field);

  void disconnect() => _service.disconnect();

  @override
  void dispose() {
    _connSub?.cancel();
    _snapSub?.cancel();
    _editSub?.cancel();
    _presenceSub?.cancel();
    _errorSub?.cancel();
    _service.dispose();
    super.dispose();
  }
}
