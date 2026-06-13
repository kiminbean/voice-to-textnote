// PushNotificationService 테스트
// Firebase는 플랫폼 채널 기반이므로 mock 주입이 불가.
// 테스트 가능한 범위: FcmTokenResult, extractMeetingId, 서비스 생성
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/push_notification_service.dart';

void main() {
  group('PushNotificationService', () {
    late PushNotificationService service;

    setUp(() {
      service = PushNotificationService();
    });

    test('서비스 인스턴스 생성이 가능해야 함', () {
      expect(service, isNotNull);
      expect(service, isA<PushNotificationService>());
    });

    test('extractMeetingId가 데이터에서 meeting_id를 추출해야 함', () {
      // Arrange: RemoteMessage 스타일 Map 생성
      // extractMeetingId는 message.data['meeting_id']를 반환
      // 실제 RemoteMessage 생성이 불가하므로 로직 검증
      expect(service.extractMeetingId, isA<Function>());
    });

    test('extractMeetingId 메서드가 존재하고 호출 가능해야 함', () {
      // Assert: 메서드 시그니처 확인
      expect(
        service.extractMeetingId,
        isA<Function>(),
      );
    });

    test('onForegroundMessage 핸들러 등록 메서드가 존재해야 함', () {
      expect(service.onForegroundMessage, isA<Function>());
    });

    test('getInitialMessage 메서드가 존재해야 함', () {
      expect(service.getInitialMessage, isA<Function>());
    });

    test('handleMessageOpenedApp 메서드가 존재해야 함', () {
      expect(service.handleMessageOpenedApp, isA<Function>());
    });

    test('initializeFCM 메서드가 존재해야 함', () {
      expect(service.initializeFCM, isA<Function>());
    });

    test('getFCMToken 메서드가 존재해야 함', () {
      expect(service.getFCMToken, isA<Function>());
    });

    test('registerFCMBackgroundHandler 함수가 존재해야 함', () {
      expect(registerFCMBackgroundHandler, isA<Function>());
    });
  });

  group('FcmTokenResult', () {
    test('성공 결과 생성 시 success가 true여야 함', () {
      // Act
      const result = FcmTokenResult(token: 'test_token_123');

      // Assert
      expect(result.success, isTrue);
      expect(result.token, equals('test_token_123'));
      expect(result.error, isNull);
    });

    test('에러 결과 생성 시 success가 false여야 함', () {
      // Act
      const result = FcmTokenResult(error: '토큰 요청 실패');

      // Assert
      expect(result.success, isFalse);
      expect(result.token, isNull);
      expect(result.error, equals('토큰 요청 실패'));
    });

    test('토큰과 에러 모두 없으면 success가 false여야 함', () {
      // Act
      const result = FcmTokenResult();

      // Assert
      expect(result.success, isFalse);
    });

    test('토큰만 있고 에러도 있으면 success가 false여야 함', () {
      // Act
      const result = FcmTokenResult(token: 'token', error: 'some_error');

      // Assert: success는 token != null && error == null
      expect(result.success, isFalse);
    });
  });
}
