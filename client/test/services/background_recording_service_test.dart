// BackgroundRecordingService 테스트
// SPEC-MOBILE-005: 인터럽션 상태, RecordConfig 고도화, 라우트 변경 검증 추가
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:audio_session/audio_session.dart';
import 'package:record/record.dart';
import 'package:voice_to_textnote/services/background_recording_service.dart';

void main() {
  // MethodChannel 사용을 위해 바인딩 초기화
  TestWidgetsFlutterBinding.ensureInitialized();

  group('BackgroundRecordingConfig', () {
    test('기본 설정으로 생성해야 함', () {
      const config = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
      );

      expect(config.filePath, equals('/test/path.m4a'));
      expect(config.flushInterval, equals(const Duration(seconds: 10)));
    });

    test('커스텀 플러시 간격으로 생성해야 함', () {
      const config = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(seconds: 5),
      );

      expect(config.flushInterval, equals(const Duration(seconds: 5)));
    });

    test('filePath이 필수 매개변수여야 함', () {
      const config = BackgroundRecordingConfig(filePath: '/test/audio.m4a');
      expect(config.filePath, isNotEmpty);
    });

    test('동일한 설정으로 equality 비교 시 동등해야 함', () {
      const config1 = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(seconds: 5),
      );
      const config2 = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(seconds: 5),
      );

      expect(config1.filePath, equals(config2.filePath));
      expect(config1.flushInterval, equals(config2.flushInterval));
    });
  });

  group('BackgroundRecordingService - DI 없이 테스트 가능한 범위', () {
    late BackgroundRecordingService service;

    setUp(() {
      service = BackgroundRecordingService();
    });

    tearDown(() {
      service.dispose();
    });

    test('초기 상태에서 stopRecording 호출 시 null을 반환해야 함', () async {
      final path = await service.stopRecording();
      expect(path, isNull);
    });

    test('초기 상태에서 isRecording이 false를 반환해야 함', () async {
      final recording = await service.isRecording();
      expect(recording, isFalse);
    });

    test('dispose 호출 시 예외가 발생하지 않아야 함', () {
      expect(() => service.dispose(), returnsNormally);
    });

    test('dispose를 여러 번 호출해도 안전해야 함', () {
      expect(() {
        service.dispose();
        service.dispose();
        service.dispose();
      }, returnsNormally);
    });

    test('dispose 후 stopRecording 호출 시 null을 반환해야 함', () async {
      service.dispose();
      final path = await service.stopRecording();
      expect(path, isNull);
    });

    test('dispose 후 isRecording이 false를 반환해야 함', () async {
      service.dispose();
      final recording = await service.isRecording();
      expect(recording, isFalse);
    });
  });

  // SPEC-MOBILE-005: 인터럽션 상태 관리
  group('REQ-002: 인터럽션 상태 관리', () {
    late BackgroundRecordingService service;

    setUp(() {
      service = BackgroundRecordingService();
    });

    tearDown(() {
      service.dispose();
    });

    test('초기 상태에서 isInterrupted는 false여야 함', () {
      expect(service.isInterrupted, isFalse);
    });

    test('onInterruptionChanged 콜백을 등록할 수 있어야 함', () {
      // Arrange & Act
      InterruptionState? capturedState;
      service.onInterruptionChanged = (state) {
        capturedState = state;
      };

      // Assert: 콜백이 설정됨 (null이 아님)
      expect(service.onInterruptionChanged, isNotNull);
    });

    test('onRouteChanged 콜백을 등록할 수 있어야 함', () {
      // Arrange & Act
      String? capturedReason;
      service.onRouteChanged = (reason) {
        capturedReason = reason;
      };

      // Assert
      expect(service.onRouteChanged, isNotNull);
    });
  });

  group('BackgroundRecordingConfig - 엣지 케이스', () {
    test('빈 문자열 filePath로도 생성 가능해야 함', () {
      const config = BackgroundRecordingConfig(filePath: '');
      expect(config.filePath, isEmpty);
    });

    test('매우 짧은 플러시 간격으로 생성 가능해야 함', () {
      const config = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(milliseconds: 100),
      );
      expect(config.flushInterval, equals(const Duration(milliseconds: 100)));
    });

    test('매우 긴 플러시 간격으로 생성 가능해야 함', () {
      const config = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(hours: 1),
      );
      expect(config.flushInterval, equals(const Duration(hours: 1)));
    });
  });

  // SPEC-MOBILE-005: InterruptionState 열거형 검증
  group('InterruptionState 열거형', () {
    test('active와 interrupted 두 상태가 존재해야 함', () {
      expect(InterruptionState.values, contains(InterruptionState.active));
      expect(InterruptionState.values, contains(InterruptionState.interrupted));
    });

    test('active 상태는 interrupted와 달라야 함', () {
      expect(InterruptionState.active, isNot(equals(InterruptionState.interrupted)));
    });
  });
}
