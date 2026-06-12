// 협업 편집 WebSocket 클라이언트 서비스
// SPEC-COLLAB-001: REQ-COLLAB-030~034
import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:voice_to_textnote/config/app_config.dart';

/// 서버 → 클라이언트 메시지 타입
class CollabMessageType {
  static const String editBroadcast = 'edit_broadcast';
  static const String syncState = 'sync_state';
  static const String userJoined = 'user_joined';
  static const String userLeft = 'user_left';
  static const String pong = 'pong';
  static const String error = 'error';
  static const String rateLimited = 'rate_limited';
}

/// 협업 참여자 정보
class CollabUser {
  final String userId;
  final String displayName;
  final String color;

  const CollabUser({
    required this.userId,
    this.displayName = '',
    this.color = '',
  });

  factory CollabUser.fromJson(Map<String, dynamic> json) => CollabUser(
        userId: json['user_id'] as String? ?? '',
        displayName: json['display_name'] as String? ?? '',
        color: json['color'] as String? ?? '',
      );
}

/// 개별 필드 상태 (sync_state용)
class CollabFieldState {
  final String value;
  final String userId;
  final double serverTs;

  const CollabFieldState({
    this.value = '',
    this.userId = '',
    this.serverTs = 0.0,
  });

  factory CollabFieldState.fromJson(Map<String, dynamic> json) =>
      CollabFieldState(
        value: json['value'] as String? ?? '',
        userId: json['user_id'] as String? ?? '',
        serverTs: (json['server_ts'] as num?)?.toDouble() ?? 0.0,
      );
}

/// 서버에서 수신한 메시지 래퍼
class CollabMessage {
  final String type;
  final Map<String, dynamic> raw;

  const CollabMessage({required this.type, required this.raw});

  // edit_broadcast 편의 접근자
  String get field => raw['field'] as String? ?? '';
  String get value => raw['value'] as String? ?? '';
  String get userId => raw['user_id'] as String? ?? '';
  String get userName => raw['user_name'] as String? ?? '';
  double get serverTs => (raw['server_ts'] as num?)?.toDouble() ?? 0.0;

  // sync_state 편의 접근자
  Map<String, CollabFieldState> get fields {
    final rawFields = raw['fields'] as Map<String, dynamic>? ?? {};
    return rawFields.map((k, v) => MapEntry(
          k,
          CollabFieldState.fromJson(v as Map<String, dynamic>),
        ));
  }

  List<CollabUser> get activeUsers {
    final list = raw['active_users'] as List<dynamic>? ?? [];
    return list
        .map((u) => CollabUser.fromJson(u as Map<String, dynamic>))
        .toList();
  }
}

/// 협업 편집 WebSocket 서비스
/// REQ-COLLAB-030: web_socket_channel 기반 연결 관리
class CollabSocketService {
  final String baseUrl;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  bool _disposed = false;

  // 외부로 노출되는 이벤트 스트림
  final _messageController = StreamController<CollabMessage>.broadcast();

  /// 서버에서 수신한 메시지 스트림
  Stream<CollabMessage> get messages => _messageController.stream;

  /// 연결 상태
  bool get isConnected => _channel != null;

  CollabSocketService({String? baseUrl})
      : baseUrl = baseUrl ?? AppConfig.apiBaseUrl;

  /// WebSocket 연결 (REQ-COLLAB-030)
  /// [taskId] = room ID, [token] = JWT Access Token
  Future<void> connect(String taskId, String token) async {
    if (_disposed) return;

    // HTTP → WS 스킴 변환
    final wsBaseUrl = baseUrl
        .replaceFirst('https://', 'wss://')
        .replaceFirst('http://', 'ws://');

    final uri = Uri.parse('$wsBaseUrl/collab/$taskId/ws?token=$token');

    _channel = WebSocketChannel.connect(uri);

    // 첫 메시지로 연결 확인 (sync_state)
    try {
      await _channel!.ready;
    } catch (e) {
      _channel = null;
      rethrow;
    }

    _subscription = _channel!.stream.listen(
      (data) {
        if (data is String) {
          _handleMessage(data);
        }
      },
      onDone: () {
        _channel = null;
        _subscription = null;
      },
      onError: (Object error) {
        _channel = null;
        _subscription = null;
      },
    );
  }

  /// edit 메시지 전송 (REQ-COLLAB-031)
  void sendEdit(String field, String value) {
    _send({
      'type': 'edit',
      'field': field,
      'value': value,
      'client_ts': DateTime.now().millisecondsSinceEpoch / 1000.0,
    });
  }

  /// cursor 메시지 전송 (REQ-COLLAB-043)
  void sendCursor(String? field) {
    _send({
      'type': 'cursor',
      'field': field,
    });
  }

  /// ping 전송 (REQ-COLLAB-004)
  void sendPing() {
    _send({'type': 'ping'});
  }

  /// WebSocket 연결 해제
  void disconnect() {
    _subscription?.cancel();
    _subscription = null;
    _channel?.sink.close();
    _channel = null;
  }

  /// 리소스 정리
  void dispose() {
    _disposed = true;
    disconnect();
    _messageController.close();
  }

  void _handleMessage(String raw) {
    try {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      final type = json['type'] as String? ?? '';
      _messageController.add(CollabMessage(type: type, raw: json));
    } catch (_) {
      // 잘못된 JSON은 무시
    }
  }

  void _send(Map<String, dynamic> data) {
    _channel?.sink.add(jsonEncode(data));
  }
}
