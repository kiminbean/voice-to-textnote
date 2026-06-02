// PermissionService 테스트
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:voice_to_textnote/services/permission_service.dart';

class MockPermission extends Mock implements Permission {}

void main() {
  late PermissionService service;

  setUp(() {
    service = PermissionService();
  });

  group('PermissionService', () {
    // 마이크 권한 요청 - 허용됨
    test('마이크 권한 요청 성공 시 granted를 반환해야 함', () async {
      // Arrange
      when(() => Permission.microphone.request())
          .thenAnswer((_) async => PermissionStatus.granted);

      // Act
      final result = await service.requestMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.granted));
    });

    // 마이크 권한 요청 - 거부됨
    test('마이크 권한 요청 거부 시 denied를 반환해야 함', () async {
      // Arrange
      when(() => Permission.microphone.request())
          .thenAnswer((_) async => PermissionStatus.denied);

      // Act
      final result = await service.requestMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.denied));
    });

    // 마이크 권한 요청 - 영구 거부
    test('마이크 권한 영구 거부 시 permanentlyDenied를 반환해야 함', () async {
      // Arrange
      when(() => Permission.microphone.request())
          .thenAnswer((_) async => PermissionStatus.permanentlyDenied);

      // Act
      final result = await service.requestMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.permanentlyDenied));
    });

    // 마이크 권한 요청 - 미결정
    test('마이크 권한 미결정 시 notDetermined를 반환해야 함', () async {
      // Arrange
      when(() => Permission.microphone.request())
          .thenAnswer((_) async => PermissionStatus.restricted);

      // Act
      final result = await service.requestMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.notDetermined));
    });

    // 알림 권한 요청 - 허용됨
    test('알림 권한 요청 성공 시 granted를 반환해야 함', () async {
      // Arrange
      when(() => Permission.notification.request())
          .thenAnswer((_) async => PermissionStatus.granted);

      // Act
      final result = await service.requestNotificationPermission();

      // Assert
      expect(result, equals(PermissionStatus.granted));
    });

    // 알림 권한 요청 - 거부됨
    test('알림 권한 요청 거부 시 denied를 반환해야 함', () async {
      // Arrange
      when(() => Permission.notification.request())
          .thenAnswer((_) async => PermissionStatus.denied);

      // Act
      final result = await service.requestNotificationPermission();

      // Assert
      expect(result, equals(PermissionStatus.denied));
    });

    // 마이크 권한 확인 - 허용됨
    test('마이크 권한 확인 시 granted를 반환해야 함', () async {
      // Arrange
      when(() => Permission.microphone.status)
          .thenAnswer((_) async => PermissionStatus.granted);

      // Act
      final result = await service.checkMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.granted));
    });

    // 마이크 권한 확인 - 거부됨
    test('마이크 권한 거부 확인 시 denied를 반환해야 함', () async {
      // Arrange
      when(() => Permission.microphone.status)
          .thenAnswer((_) async => PermissionStatus.denied);

      // Act
      final result = await service.checkMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.denied));
    });

    // 마이크 권한 확인 - 영구 거부
    test('마이크 권한 영구 거부 확인 시 permanentlyDenied를 반환해야 함', () async {
      // Arrange
      when(() => Permission.microphone.status)
          .thenAnswer((_) async => PermissionStatus.permanentlyDenied);

      // Act
      final result = await service.checkMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.permanentlyDenied));
    });

    // shouldShowRationale - true
    test('권한 설명 필요 시 true를 반환해야 함', () async {
      // Arrange
      final mockPermission = MockPermission();
      when(() => mockPermission.shouldShowRequestRationale)
          .thenAnswer((_) async => true);

      // Act
      final result = await service.shouldShowRationale(mockPermission);

      // Assert
      expect(result, isTrue);
    });

    // shouldShowRationale - false
    test('권한 설명 불필요 시 false를 반환해야 함', () async {
      // Arrange
      final mockPermission = MockPermission();
      when(() => mockPermission.shouldShowRequestRationale)
          .thenAnswer((_) async => false);

      // Act
      final result = await service.shouldShowRationale(mockPermission);

      // Assert
      expect(result, isFalse);
    });

    // 상태 매핑 테스트 - 모든 케이스
    group('상태 매핑 (_mapStatus)', () {
      test('PermissionStatus.granded -> 내부 granted', () async {
        when(() => Permission.microphone.status)
            .thenAnswer((_) async => PermissionStatus.granted);
        final result = await service.checkMicrophonePermission();
        expect(result, equals(PermissionStatus.granted));
      });

      test('PermissionStatus.denied -> 내부 denied', () async {
        when(() => Permission.microphone.status)
            .thenAnswer((_) async => PermissionStatus.denied);
        final result = await service.checkMicrophonePermission();
        expect(result, equals(PermissionStatus.denied));
      });

      test('PermissionStatus.permanentlyDenied -> 내부 permanentlyDenied', () async {
        when(() => Permission.microphone.status)
            .thenAnswer((_) async => PermissionStatus.permanentlyDenied);
        final result = await service.checkMicrophonePermission();
        expect(result, equals(PermissionStatus.permanentlyDenied));
      });

      test('PermissionStatus.restricted -> 내부 notDetermined', () async {
        when(() => Permission.microphone.status)
            .thenAnswer((_) async => PermissionStatus.restricted);
        final result = await service.checkMicrophonePermission();
        expect(result, equals(PermissionStatus.notDetermined));
      });

      test('PermissionStatus.limited -> 내부 notDetermined', () async {
        when(() => Permission.microphone.status)
            .thenAnswer((_) async => PermissionStatus.limited);
        final result = await service.checkMicrophonePermission();
        expect(result, equals(PermissionStatus.notDetermined));
      });
    });

    // openAppSettings 테스트
    test('설정 열기 성공 시 true를 반환해야 함', () async {
      // Arrange
      when(() => openAppSettings()).thenAnswer((_) async => true);

      // Act
      final result = await service.openAppSettings();

      // Assert
      expect(result, isTrue);
    });

    // openAppSettings 실패 테스트
    test('설정 열기 실패 시 false를 반환해야 함', () async {
      // Arrange
      when(() => openAppSettings()).thenAnswer((_) async => false);

      // Act
      final result = await service.openAppSettings();

      // Assert
      expect(result, isFalse);
    });
  });
}
