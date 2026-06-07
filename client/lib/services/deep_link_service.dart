// SPEC-MOBILE-001: 딥링크 서비스
// REQ-MOBILE-006-01~05: Push 알림 및 외부 링크를 통한 앱 내 네비게이션
//
// 처리 시나리오:
// 1. Cold start: 앱 종료 상태 → getInitialMessage()
// 2. Background: 앱 백그라운드 → onMessageOpenedApp
// 3. Foreground: 앱 사용 중 → flutter_local_notifications callback
// 4. URL Scheme: voicetextnote://summary/{id} 외부 링크

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:go_router/go_router.dart';

/// 딥링크 대상 화면 경로 상수
class DeepLinkRoutes {
  static const String summary = '/result';
  static const String home = '/';
}

/// 딥링크 서비스
/// Push 알림 payload와 URL Scheme을 파싱하여 go_router로 네비게이션합니다.
class DeepLinkService {
  DeepLinkService._();
  static final DeepLinkService instance = DeepLinkService._();

  /// URL Scheme 접두사
  static const _scheme = 'voicetextnote://';

  /// 보류 중인 딥링크 (라우터 초기화 전 수신된 경우)
  String? _pendingDeeplink;

  /// go_router 인스턴스 (초기화 후 설정)
  GoRouter? _router;

  /// go_router 설정
  void setRouter(GoRouter router) {
    _router = router;

    // 보류 중인 딥링크가 있으면 즉시 실행
    if (_pendingDeeplink != null) {
      final path = _pendingDeeplink!;
      _pendingDeeplink = null;
      navigateToPath(path);
    }
  }

  /// Cold start 처리
  /// 앱이 완전히 종료된 상태에서 Push 알림으로 시작될 때 호출
  Future<void> handleColdStart() async {
    try {
      final message = await FirebaseMessaging.instance.getInitialMessage();
      if (message != null) {
        final path = _extractPathFromMessage(message);
        if (path != null) {
          debugPrint('DeepLink: cold start → $path');
          navigateToPath(path);
        }
      }
    } catch (e) {
      debugPrint('DeepLink cold start 처리 실패: $e');
    }
  }

  /// Background resume 처리
  /// 앱이 백그라운드에 있을 때 Push 알림으로 resume되는 경우
  void handleBackgroundResume() {
    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      final path = _extractPathFromMessage(message);
      if (path != null) {
        debugPrint('DeepLink: background resume → $path');
        navigateToPath(path);
      }
    });
  }

  /// Foreground 알림 응답 처리
  /// flutter_local_notifications의 onDidReceiveNotificationResponse에서 호출
  void handleForegroundNotification(String? payload) {
    if (payload == null || payload.isEmpty) return;

    final path = _extractPathFromPayload(payload);
    if (path != null) {
      debugPrint('DeepLink: foreground notification → $path');
      navigateToPath(path);
    }
  }

  /// URL Scheme 처리
  /// voicetextnote://summary/{id} 형태의 외부 링크
  void handleUrlScheme(String url) {
    final path = _convertSchemeToPath(url);
    if (path != null) {
      debugPrint('DeepLink: URL scheme → $path');
      navigateToPath(path);
    }
  }

  /// 경로로 네비게이션
  void navigateToPath(String path) {
    if (_router == null) {
      // 라우터가 아직 초기화되지 않은 경우 보류
      _pendingDeeplink = path;
      debugPrint('DeepLink: 라우터 미초기화, 보류 → $path');
      return;
    }

    try {
      _router!.go(path);
    } catch (e) {
      debugPrint('DeepLink 네비게이션 실패: $e');
      // fallback: 홈으로 이동
      _router!.go(DeepLinkRoutes.home);
    }
  }

  /// RemoteMessage에서 meeting_id 추출 후 경로 생성
  String? _extractPathFromMessage(RemoteMessage message) {
    final meetingId = message.data['meeting_id'] as String?;
    if (meetingId == null || meetingId.isEmpty) return null;

    final type = message.data['type'] as String?;
    return _buildPath(meetingId: meetingId, type: type);
  }

  /// Notification payload에서 경로 생성
  /// payload 형식: "meeting_id=xxx" 또는 JSON
  String? _extractPathFromPayload(String payload) {
    // 형식 1: meeting_id=xxx
    if (payload.startsWith('meeting_id=')) {
      final meetingId = payload.substring('meeting_id='.length);
      return _buildPath(meetingId: meetingId);
    }

    // 형식 2: 단순 meeting_id
    if (!payload.contains('=') && !payload.contains('{')) {
      return _buildPath(meetingId: payload);
    }

    return null;
  }

  /// URL Scheme을 내부 경로로 변환
  /// voicetextnote://summary/abc123 → /result/abc123
  String? _convertSchemeToPath(String url) {
    if (!url.startsWith(_scheme)) return null;

    final path = url.substring(_scheme.length);

    // summary/{id} → /result/{id}
    if (path.startsWith('summary/')) {
      final id = path.substring('summary/'.length);
      if (id.isNotEmpty) {
        return _buildPath(meetingId: id);
      }
    }

    // result/{id} → /result/{id}
    if (path.startsWith('result/')) {
      final id = path.substring('result/'.length);
      if (id.isNotEmpty) {
        return _buildPath(meetingId: id);
      }
    }

    return null;
  }

  /// 내부 경로 생성
  String _buildPath({required String meetingId, String? type}) {
    return '${DeepLinkRoutes.summary}/$meetingId';
  }

  /// 딥링크 URL이 유효한지 검증
  bool isValidDeeplink(String url) {
    if (!url.startsWith(_scheme)) return false;

    final path = url.substring(_scheme.length);
    return path.startsWith('summary/') || path.startsWith('result/');
  }
}
