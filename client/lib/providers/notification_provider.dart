// 푸시 알림 상태 프로바이더
// @MX:ANCHOR: FCM 토큰 및 알림 수신 상태 관리
// @MX:REASON: 앱 전역에서 FCM 토큰 필요 시 참조 (auth_provider, api_client)

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/push_notification_service.dart';
import 'package:voice_to_textnote/services/permission_service.dart';
import 'package:voice_to_textnote/services/device_api.dart';

/// 알림 상태
class NotificationState {
  final String? fcmToken;
  final bool isInitialized;
  final String? error;

  const NotificationState({
    this.fcmToken,
    this.isInitialized = false,
    this.error,
  });

  const NotificationState.initial()
      : fcmToken = null,
        isInitialized = false,
        error = null;

  NotificationState copyWith({
    String? fcmToken,
    bool? isInitialized,
    String? error,
  }) {
    return NotificationState(
      fcmToken: fcmToken ?? this.fcmToken,
      isInitialized: isInitialized ?? this.isInitialized,
      error: error ?? this.error,
    );
  }
}

/// 알림 Notifier
class NotificationNotifier extends StateNotifier<NotificationState> {
  final PushNotificationService _pushService;
  final PermissionService _permissionService;
  final DeviceApi _deviceApi;

  // 마지막 알림 데이터 저장 (딥링크용)
  String? _lastMeetingId;

  NotificationNotifier(this._pushService, this._permissionService, this._deviceApi)
      : super(const NotificationState.initial());

  /// FCM 초기화 및 토큰 요청
  Future<void> initialize() async {
    try {
      // 마이크/알림 권한 요청
      await _permissionService.requestMicrophonePermission();
      await _permissionService.requestNotificationPermission();

      // FCM 초기화
      final initialized = await _pushService.initializeFCM();
      if (!initialized) {
        state = state.copyWith(error: 'FCM 초기화 실패');
        return;
      }

      // FCM 토큰 조회
      final tokenResult = await _pushService.getFCMToken();
      if (tokenResult.success) {
        state = state.copyWith(
          fcmToken: tokenResult.token,
          isInitialized: true,
        );
        
        // 백엔드에 디바이스 토큰 등록
        try {
          await _deviceApi.registerDeviceToken(tokenResult.token!);
        } catch (e) {
          debugPrint('디바이스 토큰 등록 실패: $e');
        }
      } else {
        state = state.copyWith(error: tokenResult.error);
      }

      // 포그라운드 메시지 핸들러 등록
      _pushService.onForegroundMessage((message) {
        // meeting_id 추출 및 저장
        final meetingId = _pushService.extractMeetingId(message);
        if (meetingId != null) {
          _lastMeetingId = meetingId;
        }
      });

      // 백그라운드/종료 상태 알림 탭 핸들러 등록
      await _pushService.handleMessageOpenedApp();
    } catch (e) {
      state = state.copyWith(error: '알림 초기화 실패: $e');
    }
  }

  /// 콜드 스타트 메시지 확인 (앱 종료 상태에서 알림 탭)
  Future<String?> checkInitialMessage() async {
    try {
      final initialMessage = await _pushService.getInitialMessage();
      if (initialMessage != null) {
        final meetingId = _pushService.extractMeetingId(initialMessage);
        if (meetingId != null) {
          _lastMeetingId = meetingId;
          return meetingId;
        }
      }
      return null;
    } catch (e) {
      debugPrint('초기 메시지 확인 실패: $e');
      return null;
    }
  }

  /// 마지막 알림 meeting_id 반환 및 초기화
  String? consumeLastMeetingId() {
    final meetingId = _lastMeetingId;
    _lastMeetingId = null;
    return meetingId;
  }
}

/// 알림 상태 프로바이더
final notificationProvider =
    StateNotifierProvider<NotificationNotifier, NotificationState>((ref) {
  return NotificationNotifier(
    ref.watch(pushNotificationServiceProvider),
    ref.watch(permissionServiceProvider),
    ref.watch(deviceApiProvider),
  );
});

/// FCM 토큰 파생 프로바이더
final fcmTokenProvider = Provider<String?>((ref) {
  return ref.watch(notificationProvider).fcmToken;
});

/// 푸시 서비스 프로바이더
final pushNotificationServiceProvider = Provider<PushNotificationService>((ref) {
  return PushNotificationService();
});

/// 권한 서비스 프로바이더
final permissionServiceProvider = Provider<PermissionService>((ref) {
  return PermissionService();
});
