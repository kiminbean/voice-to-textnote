// BackgroundRecordingService 테스트
// 서비스가 내부에서 AudioRecorder를 생성하므로 DI 없이 테스트 가능한 범위만 검증
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:audio_session/audio_session.dart';
import 'package:record/record.dart';
import 'package:voice_to_textnote/services/background_recording_service.dart';

void main() {
  group('BackgroundRecordingConfig', () {
    test('기본 설정으로 생성해야 함', () {
      // Arrange & Act
      const config = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
      );

      // Assert
      expect(config.filePath, equals('/test/path.m4a'));
      expect(config.flushInterval, equals(const Duration(seconds: 10)));
    });

    test('커스텀 플러시 간격으로 생성해야 함', () {
      // Arrange & Act
      const config = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(seconds: 5),
      );

      // Assert
      expect(config.flushInterval, equals(const Duration(seconds: 5)));
    });

    test('filePath이 필수 매개변수여야 함', () {
      // Assert: named parameter required
      // 컴파일 타임에 확인됨 - 생성자에 filePath 누락 시 에러
      const config = BackgroundRecordingConfig(filePath: '/test/audio.m4a');
      expect(config.filePath, isNotEmpty);
    });

    test('동일한 설정으로 equality 비교 시 동등해야 함', () {
      // Arrange
      const config1 = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(seconds: 5),
      );
      const config2 = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(seconds: 5),
      );

      // Assert
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
      // Act: 녹음 시작 없이 바로 중지
      final path = await service.stopRecording();

      // Assert
      expect(path, isNull);
    });

    test('초기 상태에서 isRecording이 false를 반환해야 함', () async {
      // Act
      final recording = await service.isRecording();

      // Assert
      expect(recording, isFalse);
    });

    test('dispose 호출 시 예외가 발생하지 않아야 함', () {
      // Act & Assert: 예외 없이 정상 종료
      expect(() => service.dispose(), returnsNormally);
    });

    test('dispose를 여러 번 호출해도 안전해야 함', () {
      // Act & Assert
      expect(() {
        service.dispose();
        service.dispose();
        service.dispose();
      }, returnsNormally);
    });

    test('dispose 후 stopRecording 호출 시 null을 반환해야 함', () async {
      // Act
      service.dispose();
      final path = await service.stopRecording();

      // Assert
      expect(path, isNull);
    });

    test('dispose 후 isRecording이 false를 반환해야 함', () async {
      // Act
      service.dispose();
      final recording = await service.isRecording();

      // Assert
      expect(recording, isFalse);
    });
  });

  group('BackgroundRecordingConfig - 엣지 케이스', () {
    test('빈 문자열 filePath로도 생성 가능해야 함', () {
      // Act
      const config = BackgroundRecordingConfig(filePath: '');

      // Assert
      expect(config.filePath, isEmpty);
    });

    test('매우 짧은 플러시 간격으로 생성 가능해야 함', () {
      // Act
      const config = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(milliseconds: 100),
      );

      // Assert
      expect(config.flushInterval, equals(const Duration(milliseconds: 100)));
    });

    test('매우 긴 플러시 간격으로 생성 가능해야 함', () {
      // Act
      const config = BackgroundRecordingConfig(
        filePath: '/test/path.m4a',
        flushInterval: Duration(hours: 1),
      );

      // Assert
      expect(config.flushInterval, equals(const Duration(hours: 1)));
    });
  });
}
