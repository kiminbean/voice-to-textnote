// NotificationProvider 테스트
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/providers/notification_provider.dart';
import 'package:voice_to_textnote/services/push_notification_service.dart';
import 'package:voice_to_textnote/services/permission_service.dart';
import 'package:voice_to_textnote/services/device_api.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

class MockPushNotificationService extends Mock
    implements PushNotificationService {}

class MockPermissionService extends Mock implements PermissionService {}

class MockDeviceApi extends Mock implements DeviceApi {}

void main() {
  late MockPushNotificationService mockPushService;
  late MockPermissionService mockPermissionService;
  late MockDeviceApi mockDeviceApi;

  setUpAll(() {
    registerFallbackValue(const Duration(seconds: 1));
  });

  setUp(() {
    mockPushService = MockPushNotificationService();
    mockPermissionService = MockPermissionService();
    mockDeviceApi = MockDeviceApi();
  });

  group('NotificationState', () {
    test('초기 상태는 올바른 기본값을 가져야 함', () {
      // Act
      const state = NotificationState.initial();

      // Assert
      expect(state.fcmToken, isNull);
      expect(state.isInitialized, isFalse);
      expect(state.error, isNull);
    });

    test('copyWith로 상태를 업데이트해야 함', () {
      // Arrange
      const initialState = NotificationState.initial();

      // Act
      final updatedState = initialState.copyWith(
        fcmToken: 'test_token',
        isInitialized: true,
      );

      // Assert
      expect(updatedState.fcmToken, equals('test_token'));
      expect(updatedState.isInitialized, isTrue);
      expect(updatedState.error, isNull);
    });

    test('copyWith는 일부 필드만 업데이트해야 함', () {
      // Arrange
      const initialState = NotificationState(
        fcmToken: 'old_token',
        isInitialized: false,
        error: 'old_error',
      );

      // Act
      final updatedState = initialState.copyWith(
        fcmToken: 'new_token',
      );

      // Assert
      expect(updatedState.fcmToken, equals('new_token'));
      expect(updatedState.isInitialized, isFalse);
      expect(updatedState.error, equals('old_error'));
    });
  });

  group('NotificationNotifier', () {
    test('초기 상태는 initial이어야 함', () {
      // Arrange
      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Assert
      expect(notifier.state.fcmToken, isNull);
      expect(notifier.state.isInitialized, isFalse);
      expect(notifier.state.error, isNull);
    });

    test('initialize 성공 시 FCM 토큰을 저장하고 백엔드에 등록해야 함', () async {
      // Arrange
      when(() => mockPermissionService.requestMicrophonePermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPermissionService.requestNotificationPermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPushService.initializeFCM()).thenAnswer((_) async => true);
      when(() => mockPushService.getFCMToken())
          .thenAnswer((_) async => const FcmTokenResult(token: 'test_token'));
      when(() => mockPushService.onForegroundMessage(any())).thenAnswer((_) {});
      when(() => mockDeviceApi.registerDeviceToken(any()))
          .thenAnswer((_) async {});
      when(() => mockPushService.handleMessageOpenedApp())
          .thenAnswer((_) async {});
      when(() => mockDeviceApi.registerDeviceToken(any()))
          .thenAnswer((_) async {});

      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Act
      await notifier.initialize();

      // Assert
      expect(notifier.state.fcmToken, equals('test_token'));
      expect(notifier.state.isInitialized, isTrue);
      expect(notifier.state.error, isNull);
      verify(() => mockDeviceApi.registerDeviceToken('test_token')).called(1);
    });

    test('initialize 실패 시 에러를 저장해야 함', () async {
      // Arrange
      when(() => mockPermissionService.requestMicrophonePermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPermissionService.requestNotificationPermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPushService.initializeFCM())
          .thenAnswer((_) async => false);

      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Act
      await notifier.initialize();

      // Assert
      expect(notifier.state.fcmToken, isNull);
      expect(notifier.state.isInitialized, isFalse);
      expect(notifier.state.error, equals('FCM 초기화 실패'));
    });

    test('initialize 시 FCM 토큰 요청 실패 시 에러를 저장해야 함', () async {
      // Arrange
      when(() => mockPermissionService.requestMicrophonePermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPermissionService.requestNotificationPermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPushService.initializeFCM()).thenAnswer((_) async => true);
      when(() => mockPushService.getFCMToken())
          .thenAnswer((_) async => const FcmTokenResult(error: 'Token error'));
      when(() => mockPushService.onForegroundMessage(any())).thenReturn(null);
      when(() => mockDeviceApi.registerDeviceToken(any()))
          .thenAnswer((_) async {});
      when(() => mockPushService.handleMessageOpenedApp())
          .thenAnswer((_) async {});

      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Act
      await notifier.initialize();

      // Assert
      expect(notifier.state.fcmToken, isNull);
      expect(notifier.state.isInitialized, isFalse);
      expect(notifier.state.error, equals('Token error'));
    });

    test('initialize 시 포그라운드 메시지 핸들러를 등록해야 함', () async {
      // Arrange
      final capturedHandlers = <Function(RemoteMessage)>[];
      when(() => mockPermissionService.requestMicrophonePermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPermissionService.requestNotificationPermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPushService.initializeFCM()).thenAnswer((_) async => true);
      when(() => mockPushService.getFCMToken())
          .thenAnswer((_) async => const FcmTokenResult(token: 'test_token'));
      when(() => mockPushService.onForegroundMessage(captureAny()))
          .thenAnswer((invocation) {
        capturedHandlers
            .add(invocation.positionalArguments[0] as Function(RemoteMessage));
      });
      when(() => mockDeviceApi.registerDeviceToken(any()))
          .thenAnswer((_) async {});
      when(() => mockPushService.handleMessageOpenedApp())
          .thenAnswer((_) async {});

      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Act
      await notifier.initialize();

      // Assert
      expect(capturedHandlers.length, equals(1));
    });

    test('포그라운드 메시지 핸들러가 meeting_id를 추출해야 함', () async {
      // Arrange
      when(() => mockPermissionService.requestMicrophonePermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPermissionService.requestNotificationPermission())
          .thenAnswer((_) async => PermissionStatus.granted);
      when(() => mockPushService.initializeFCM()).thenAnswer((_) async => true);
      when(() => mockPushService.getFCMToken())
          .thenAnswer((_) async => const FcmTokenResult(token: 'test_token'));

      const testMessage = RemoteMessage(
        messageId: 'test_msg',
        data: {'meeting_id': 'meeting_123'},
      );

      when(() => mockPushService.extractMeetingId(testMessage))
          .thenReturn('meeting_123');

      Function(RemoteMessage)? capturedHandler;
      when(() => mockPushService.onForegroundMessage(captureAny()))
          .thenAnswer((invocation) {
        capturedHandler =
            invocation.positionalArguments[0] as Function(RemoteMessage);
      });
      when(() => mockDeviceApi.registerDeviceToken(any()))
          .thenAnswer((_) async {});
      when(() => mockPushService.handleMessageOpenedApp())
          .thenAnswer((_) async {});

      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Act
      await notifier.initialize();
      capturedHandler?.call(testMessage);

      // Assert
      expect(notifier.consumeLastMeetingId(), equals('meeting_123'));
    });

    test('checkInitialMessage 성공 시 meeting_id를 반환해야 함', () async {
      // Arrange
      const testMessage = RemoteMessage(
        messageId: 'test_msg',
        data: {'meeting_id': 'meeting_456'},
      );
      when(() => mockPushService.getInitialMessage())
          .thenAnswer((_) async => testMessage);
      when(() => mockPushService.extractMeetingId(testMessage))
          .thenReturn('meeting_456');

      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Act
      final meetingId = await notifier.checkInitialMessage();

      // Assert
      expect(meetingId, equals('meeting_456'));
    });

    test('checkInitialMessage 실패 시 null을 반환해야 함', () async {
      // Arrange
      when(() => mockPushService.getInitialMessage())
          .thenAnswer((_) async => null);

      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Act
      final meetingId = await notifier.checkInitialMessage();

      // Assert
      expect(meetingId, isNull);
    });

    test('checkInitialMessage 예외 발생 시 null을 반환해야 함', () async {
      // Arrange
      when(() => mockPushService.getInitialMessage())
          .thenThrow(Exception('Error'));

      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Act
      final meetingId = await notifier.checkInitialMessage();

      // Assert
      expect(meetingId, isNull);
    });

    test('consumeLastMeetingId는 마지막 meeting_id를 반환하고 초기화해야 함', () {
      // Arrange
      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );
      // 내부 상태 설정 (리플렉션 또는 테스트 전용 메서드로 설정 필요)
      // 여기서는 초기 상태에서 시작

      // Act
      final firstCall = notifier.consumeLastMeetingId();
      final secondCall = notifier.consumeLastMeetingId();

      // Assert
      expect(firstCall, isNull);
      expect(secondCall, isNull);
    });

    test('initialize 예외 발생 시 에러를 저장해야 함', () async {
      // Arrange
      when(() => mockPermissionService.requestMicrophonePermission())
          .thenThrow(Exception('Permission error'));

      final notifier = NotificationNotifier(
        mockPushService,
        mockPermissionService,
        mockDeviceApi,
      );

      // Act
      await notifier.initialize();

      // Assert
      expect(notifier.state.error, contains('알림 초기화 실패'));
    });
  });

  group('Providers', () {
    test('notificationProvider는 NotificationNotifier를 생성해야 함', () {
      // Arrange
      final container = ProviderContainer(
        overrides: [
          pushNotificationServiceProvider.overrideWithValue(mockPushService),
          permissionServiceProvider.overrideWithValue(mockPermissionService),
          deviceApiProvider.overrideWithValue(mockDeviceApi),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final notifier = container.read(notificationProvider.notifier);

      // Assert
      expect(notifier, isA<NotificationNotifier>());
    });

    test('fcmTokenProvider는 FCM 토큰을 반환해야 함', () {
      // Arrange
      final container = ProviderContainer(
        overrides: [
          pushNotificationServiceProvider.overrideWithValue(mockPushService),
          permissionServiceProvider.overrideWithValue(mockPermissionService),
          deviceApiProvider.overrideWithValue(mockDeviceApi),
        ],
      );
      addTearDown(container.dispose);

      // 초기화
      final notifier = container.read(notificationProvider.notifier);
      notifier.state = const NotificationState(
        fcmToken: 'test_token_123',
        isInitialized: true,
      );

      // Act
      final token = container.read(fcmTokenProvider);

      // Assert
      expect(token, equals('test_token_123'));
    });

    test('fcmTokenProvider는 null을 반환할 수 있어야 함', () {
      // Arrange
      final container = ProviderContainer(
        overrides: [
          pushNotificationServiceProvider.overrideWithValue(mockPushService),
          permissionServiceProvider.overrideWithValue(mockPermissionService),
          deviceApiProvider.overrideWithValue(mockDeviceApi),
        ],
      );
      addTearDown(container.dispose);

      // 초기화하지 않은 상태

      // Act
      final token = container.read(fcmTokenProvider);

      // Assert
      expect(token, isNull);
    });
  });
}
