// NotificationService 상수 및 안전성 테스트
// SPEC-APP-005 REQ-015
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/notification_service.dart';

void main() {
  group('NotificationService 인스턴스', () {
    test('인스턴스를 생성할 수 있어야 함', () {
      final service = NotificationService();

      expect(service, isNotNull);
    });

    test('여러 인스턴스를 독립적으로 생성할 수 있어야 함', () {
      final service1 = NotificationService();
      final service2 = NotificationService();

      expect(identical(service1, service2), isFalse);
    });
  });
}
