// SPEC-COLLAB-001: 실시간 공동 편집 WebSocket 클라이언트
import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'package:voice_to_textnote/services/auth_service.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

final collabServiceProvider = Provider<CollabService>((ref) {
  return CollabService(ref.watch(authServiceProvider));
});

enum CollabConnectionState { disconnected, connecting, connected, error }

class PresenceUser {
  final String userId;
  final String displayName;
  final String? avatarUrl;
  final String? activeField;

  const PresenceUser({
    required this.userId,
    required this.displayName,
    this.avatarUrl,
    this.activeField,
  });

  factory PresenceUser.fromJson(Map<String, dynamic> json) {
    return PresenceUser(
      userId: json['user_id'] as String,
      displayName: json['display_name'] as String? ?? '',
      avatarUrl: json['avatar_url'] as String?,
      activeField: json['active_field'] as String?,
    );
  }
}

class CollabSnapshot {
  final Map<String, dynamic> document;
  final Map<String, DateTime> fieldTimestamps;
  final List<PresenceUser> presence;

  const CollabSnapshot({
    required this.document,
    required this.fieldTimestamps,
    required this.presence,
  });
}

class CollabEditEvent {
  final String userId;
  final String field;
  final dynamic value;
  final DateTime serverTimestamp;
  final bool applied;

  const CollabEditEvent({
    required this.userId,
    required this.field,
    required this.value,
    required this.serverTimestamp,
    required this.applied,
  });
}

class CollabAck {
  final String field;
  final DateTime serverTimestamp;
  final bool applied;

  const CollabAck({
    required this.field,
    required this.serverTimestamp,
    required this.applied,
  });
}

class CollabService {
  final AuthService _authService;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  bool _disposed = false;

  final _connectionController = StreamController<CollabConnectionState>.broadcast();
  final _snapshotController = StreamController<CollabSnapshot>.broadcast();
  final _editController = StreamController<CollabEditEvent>.broadcast();
  final _presenceController = StreamController<List<PresenceUser>>.broadcast();
  final _ackController = StreamController<CollabAck>.broadcast();
  final _errorController = StreamController<String>.broadcast();

  Stream<CollabConnectionState> get onConnectionChange => _connectionController.stream;
  Stream<CollabSnapshot> get onSnapshot => _snapshotController.stream;
  Stream<CollabEditEvent> get onEdit => _editController.stream;
  Stream<List<PresenceUser>> get onPresenceChange => _presenceController.stream;
  Stream<CollabAck> get onAck => _ackController.stream;
  Stream<String> get onError => _errorController.stream;

  CollabConnectionState _state = CollabConnectionState.disconnected;
  CollabConnectionState get connectionState => _state;

  CollabService(this._authService);

  String _buildWsUrl(String taskId) {
    final baseUrl = AppConfig.apiBaseUrl;
    final wsScheme = baseUrl.startsWith('https') ? 'wss' : 'ws';
    final httpUrl = baseUrl.replaceFirst(RegExp(r'^https?'), wsScheme);
    return '$httpUrl/collab/$taskId/ws';
  }

  Future<void> connect(String taskId) async {
    if (_state == CollabConnectionState.connecting ||
        _state == CollabConnectionState.connected) {
      return;
    }

    _setState(CollabConnectionState.connecting);

    final token = await _authService.getAccessToken();
    if (token == null) {
      _setError('인증 토큰이 없습니다');
      return;
    }

    final url = Uri.parse('${_buildWsUrl(taskId)}?token=$token');
    try {
      _channel = WebSocketChannel.connect(url);
      _subscription = _channel!.stream.listen(
        _onMessage,
        onError: (e) => _setError('WebSocket 오류: $e'),
        onDone: () {
          if (!_disposed) {
            _setState(CollabConnectionState.disconnected);
          }
        },
      );
    } catch (e) {
      _setError('연결 실패: $e');
    }
  }

  void _onMessage(dynamic data) {
    try {
      final msg = jsonDecode(data as String) as Map<String, dynamic>;
      final type = msg['type'] as String;
      final payload = msg['payload'] as Map<String, dynamic>? ?? {};

      switch (type) {
        case 'snapshot':
          _handleSnapshot(payload);
          break;
        case 'edit':
          _handleEdit(payload);
          break;
        case 'presence':
          _handlePresence(payload);
          break;
        case 'cursor':
          break;
        case 'ack':
          _handleAck(payload);
          break;
        case 'error':
          _errorController.add(payload['detail'] as String? ?? '알 수 없는 오류');
          break;
      }
    } catch (e) {
      _errorController.add('메시지 파싱 오류: $e');
    }
  }

  void _handleSnapshot(Map<String, dynamic> payload) {
    _setState(CollabConnectionState.connected);

    final rawTs = payload['field_timestamps'] as Map<String, dynamic>? ?? {};
    final timestamps = <String, DateTime>{};
    for (final entry in rawTs.entries) {
      try {
        timestamps[entry.key] = DateTime.parse(entry.value as String);
      } catch (_) {}
    }

    final rawPresence = payload['presence'] as List? ?? [];
    final presence = rawPresence
        .map((e) => PresenceUser.fromJson(e as Map<String, dynamic>))
        .toList();

    _snapshotController.add(CollabSnapshot(
      document: payload['document'] as Map<String, dynamic>? ?? {},
      fieldTimestamps: timestamps,
      presence: presence,
    ));
    _presenceController.add(presence);
  }

  void _handleEdit(Map<String, dynamic> payload) {
    _editController.add(CollabEditEvent(
      userId: payload['user_id'] as String,
      field: payload['field'] as String,
      value: payload['value'],
      serverTimestamp: DateTime.parse(payload['server_timestamp'] as String),
      applied: payload['applied'] as bool? ?? true,
    ));
  }

  void _handlePresence(Map<String, dynamic> payload) {
    final rawList = payload['presence'] as List? ?? [];
    final list = rawList
        .map((e) => PresenceUser.fromJson(e as Map<String, dynamic>))
        .toList();
    _presenceController.add(list);
  }

  void _handleAck(Map<String, dynamic> payload) {
    _ackController.add(CollabAck(
      field: payload['field'] as String,
      serverTimestamp: DateTime.parse(payload['server_timestamp'] as String),
      applied: payload['applied'] as bool? ?? true,
    ));
  }

  void sendEdit(String field, dynamic value) {
    _send({
      'type': 'edit',
      'payload': {
        'field': field,
        'value': value,
        'client_timestamp': DateTime.now().toUtc().toIso8601String(),
      },
    });
  }

  void sendCursor(String field) {
    _send({
      'type': 'cursor',
      'payload': {'field': field},
    });
  }

  void _send(Map<String, dynamic> msg) {
    if (_channel != null && _state == CollabConnectionState.connected) {
      _channel!.sink.add(jsonEncode(msg));
    }
  }

  void _setState(CollabConnectionState newState) {
    _state = newState;
    if (!_connectionController.isClosed) {
      _connectionController.add(newState);
    }
  }

  void _setError(String message) {
    _setState(CollabConnectionState.error);
    if (!_errorController.isClosed) {
      _errorController.add(message);
    }
  }

  void disconnect() {
    _subscription?.cancel();
    _subscription = null;
    _channel?.sink.close();
    _channel = null;
    _setState(CollabConnectionState.disconnected);
  }

  void dispose() {
    _disposed = true;
    disconnect();
    _connectionController.close();
    _snapshotController.close();
    _editController.close();
    _presenceController.close();
    _ackController.close();
    _errorController.close();
  }
}
