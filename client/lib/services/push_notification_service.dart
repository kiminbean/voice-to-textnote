// FCM 푸시 알림 서비스
// @MX:ANCHOR: FCM 초기화 및 토큰 관리의 핵심 서비스
// @MX:REASON: 앱 시작 시 초기화 + 백그라운드 메시지 처리

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter/foundation.dart';

/// FCM 토큰 요청 결과
class FcmTokenResult {
  final String? token;
  final String? error;

  const FcmTokenResult({this.token, this.error});

  bool get success => token != null && error == null;
}

/// 푸시 알림 서비스
class PushNotificationService {
  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  /// FCM 초기화
  Future<bool> initializeFCM() async {
    try {
      // Firebase 초기화 확인
      if (Firebase.apps.isEmpty) {
        await Firebase.initializeApp();
      }

      // 권한 요청 (iOS)
      await _requestPermission();

      // 로컬 알림 초기화
      await _setupLocalNotifications();

      // FCM 토큰 요청
      await _subscribeToTopic();

      return true;
    } catch (e) {
      debugPrint('FCM 초기화 실패: $e');
      return false;
    }
  }

  /// FCM 토큰 조회
  Future<FcmTokenResult> getFCMToken() async {
    try {
      final token = await FirebaseMessaging.instance.getToken();
      if (token == null) {
        return const FcmTokenResult(error: 'FCM 토큰을 가져올 수 없습니다');
      }
      return FcmTokenResult(token: token);
    } catch (e) {
      return FcmTokenResult(error: 'FCM 토큰 요청 실패: $e');
    }
  }

  /// 권한 요청 (iOS)
  Future<void> _requestPermission() async {
    final settings = await FirebaseMessaging.instance.requestPermission(
      alert: true,
      announcement: false,
      badge: true,
      carPlay: false,
      criticalAlert: false,
      provisional: false,
      sound: true,
    );

    debugPrint('FCM 권한 상태: ${settings.authorizationStatus}');
  }

  /// 로컬 알림 설정 (Android 포그라운드 지원)
  Future<void> _setupLocalNotifications() async {
    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _localNotifications.initialize(initSettings);
  }

  /// 토픽 구독 (옵션)
  Future<void> _subscribeToTopic() async {
    try {
      await FirebaseMessaging.instance.subscribeToTopic('all');
      debugPrint('토픽 구독 완료: all');
    } catch (e) {
      debugPrint('토픽 구독 실패: $e');
    }
  }

  /// 포그라운드 메시지 핸들러 등록
  void onForegroundMessage(Function(RemoteMessage) handler) {
    FirebaseMessaging.onMessage.listen(handler);
  }

  /// 앱 종료 상태 메시지 확인 (콜드 스타트)
  Future<RemoteMessage?> getInitialMessage() async {
    return await FirebaseMessaging.instance.getInitialMessage();
  }

  /// 백그라운드/종료 상태에서 알림 탭 핸들러
  Future<void> handleMessageOpenedApp() async {
    // onMessageOpenedApp 스트림 구독
    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      debugPrint('알림 탭으로 앱 열림: ${message.messageId}');
      // 딥링크 처리는 호출자가 수행
    });
  }

  /// 알림 데이터에서 meeting_id 추출
  String? extractMeetingId(RemoteMessage message) {
    final data = message.data;
    return data['meeting_id'] as String?;
  }
}

/// 백그라운드 메시지 핸들러 (최상위 함수 필수)
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  debugPrint('백그라운드 메시지 수신: ${message.messageId}');
}

/// FCM 백그라운드 핸들러 등록 함수
void registerFCMBackgroundHandler() {
  FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);
}
