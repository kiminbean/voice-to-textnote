// 로컬 알림 서비스
// @MX:NOTE: SPEC-APP-005 REQ-015 — 파이프라인 완료 시 로컬 알림 표시

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// 로컬 알림 서비스 (REQ-015)
class NotificationService {
  static const String _channelId = 'pipeline_channel';
  static const String _channelName = '파이프라인 처리';
  static const String _channelDescription = '음성 처리 완료 알림';

  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();

  bool _initialized = false;

  /// 초기화
  Future<void> init() async {
    if (_initialized) return;

    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _plugin.initialize(
      settings,
      onDidReceiveNotificationResponse: (_) {
        // 알림 탭 시 처리 (MainActivity/AppDelegate에서 라우팅)
      },
    );

    _initialized = true;
  }

  /// 파이프라인 완료 알림 표시 (REQ-015)
  Future<void> showPipelineCompleted({
    required String meetingId,
    required String title,
  }) async {
    if (!_initialized) await init();

    const androidDetails = AndroidNotificationDetails(
      _channelId,
      _channelName,
      channelDescription: _channelDescription,
      importance: Importance.high,
      priority: Priority.high,
    );

    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );

    const details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    await _plugin.show(
      meetingId.hashCode,
      '처리 완료',
      '"$title" 처리가 완료되었습니다.',
      details,
    );
  }
}
