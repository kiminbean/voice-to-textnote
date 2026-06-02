// PermissionService 테스트
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:permission_handler/permission_handler.dart' as ph;
import 'package:voice_to_textnote/services/permission_service.dart';

class MockPermission extends Mock implements ph.Permission {}

void main() {
  late PermissionService service;

  setUp(() {
    service = PermissionService();
  });

  group('PermissionService', () {
    // 마이크 권한 요청 - 허용됨
    test('마이크 권한 요청 성공 시 granted를 반환해야 함', () async {
      // Arrange
      when(() => ph.Permission.microphone.request())
          .thenAnswer((_) async => ph.PermissionStatus.granted);

      // Act
      final result = await service.requestMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.granted));
    });

    // 마이크 권한 요청 - 거부됨
    test('마이크 권한 요청 거부 시 denied를 반환해야 함', () async {
      // Arrange
      when(() => ph.Permission.microphone.request())
          .thenAnswer((_) async => ph.PermissionStatus.denied);

      // Act
      final result = await service.requestMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.denied));
    });

    // 마이크 권한 요청 - 영구 거부
    test('마이크 권한 영구 거부 시 permanentlyDenied를 반환해야 함', () async {
      // Arrange
      when(() => ph.Permission.microphone.request())
          .thenAnswer((_) async => ph.PermissionStatus.permanentlyDenied);

      // Act
      final result = await service.requestMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.permanentlyDenied));
    });

    // 마이크 권한 요청 - 미결정
    test('마이크 권한 미결정 시 notDetermined를 반환해야 함', () async {
      // Arrange
      when(() => ph.Permission.microphone.request())
          .thenAnswer((_) async => ph.PermissionStatus.denied); // Will map to notDetermined

      // Act
      final result = await service.requestMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.notDetermined));
    });

    // 알림 권한 요청 - 허용됨
    test('알림 권한 요청 성공 시 granted를 반환해야 함', () async {
      // Arrange
      when(() => ph.Permission.notification.request())
          .thenAnswer((_) async => ph.PermissionStatus.granted);

      // Act
      final result = await service.requestNotificationPermission();

      // Assert
      expect(result, equals(PermissionStatus.granted));
    });

    // 알림 권한 요청 - 거부됨
    test('알림 권한 요청 거부 시 denied를 반환해야 함', () async {
      // Arrange
      when(() => ph.Permission.notification.request())
          .thenAnswer((_) async => ph.PermissionStatus.denied);

      // Act
      final result = await service.requestNotificationPermission();

      // Assert
      expect(result, equals(PermissionStatus.denied));
    });

    // 마이크 권한 확인 - 허용됨
    test('마이크 권한 확인 시 granted를 반환해야 함', () async {
      // Arrange
      when(() => ph.Permission.microphone.status)
          .thenAnswer((_) async => ph.PermissionStatus.granted);

      // Act
      final result = await service.checkMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.granted));
    });

    // 마이크 권한 확인 - 거부됨
    test('마이크 권한 거부 확인 시 denied를 반환해야 함', () async {
      // Arrange
      when(() => ph.Permission.microphone.status)
          .thenAnswer((_) async => ph.PermissionStatus.denied);

      // Act
      final result = await service.checkMicrophonePermission();

      // Assert
      expect(result, equals(PermissionStatus.denied));
    });

    // 마이크 권한 확인 - 영구 거부
    test('마이크 권한 영구 거부 확인 시 permanentlyDenied를 반환해야 함', () async {
      // Arrange
      when(() => ph.Permission.microphone.status)
          .thenAnswer((_) async => ph.PermissionStatus.permanentlyDenied);

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

    // 상태 매핑 테스트 - 기본 케이스만 (restricted/limited은 제거)
    group('상태 매핑 (_mapStatus)', () {
      test('ph.PermissionStatus.granted -> 내부 granted', () async {
        when(() => ph.Permission.microphone.status)
            .thenAnswer((_) async => ph.PermissionStatus.granted);
        final result = await service.checkMicrophonePermission();
        expect(result, equals(ph.PermissionStatus.granted));
      });

      test('ph.PermissionStatus.denied -> 내부 denied', () async {
        when(() => ph.Permission.microphone.status)
            .thenAnswer((_) async => ph.PermissionStatus.denied);
        final result = await service.checkMicrophonePermission();
        expect(result, equals(ph.PermissionStatus.denied));
      });

      test('ph.PermissionStatus.permanentlyDenied -> 내부 permanentlyDenied', () async {
        when(() => ph.Permission.microphone.status)
            .thenAnswer((_) async => ph.PermissionStatus.permanentlyDenied);
        final result = await service.checkMicrophonePermission();
        expect(result, equals(ph.PermissionStatus.permanentlyDenied));
      });
    });

    // openAppSettings 테스트
    test('설정 열기 성공 시 true를 반환해야 함', () async {
      // Arrange
      when(() => ph.openAppSettings()).thenAnswer((_) async => true);

      // Act
      final result = await service.openAppSettings();

      // Assert
      expect(result, isTrue);
    });

    // openAppSettings 실패 테스트
    test('설정 열기 실패 시 false를 반환해야 함', () async {
      // Arrange
      when(() => ph.openAppSettings()).thenAnswer((_) async => false);

      // Act
      final result = await service.openAppSettings();

      // Assert
      expect(result, isFalse);
    });
  });
}
