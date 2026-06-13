import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/mocks/mock_platform_stt_service.dart';
import 'package:voice_to_textnote/models/transcription_result.dart';
import 'package:voice_to_textnote/services/platform_stt_service.dart';

void main() {
  group('MockPlatformSttService', () {
    late MockPlatformSttService mockService;

    setUp(() {
      mockService = MockPlatformSttService();
    });

    test('mock service can be instantiated', () {
      expect(mockService, isA<MockPlatformSttService>());
      expect(mockService, isA<PlatformSttService>());
    });

    test('setupSuccessfulTranscription sets up successful transcription stub',
        () {
      mockService.setupSuccessfulTranscription(
        text: '테스트 전사 결과',
        offline: true,
      );

      expect(mockService.transcribe('/test/path.wav'), completes);
    });

    test('setupSuccessfulTranscription with default values', () async {
      mockService.setupSuccessfulTranscription();

      final result = await mockService.transcribe('/test/path.wav');

      expect(result.text, '테스트 전사 결과');
      expect(result.offline, isTrue);
    });

    test('setupFailure sets up failure stub', () async {
      mockService.setupFailure('Network timeout');

      expect(
        () => mockService.transcribe('/test/path.wav'),
        throwsA(isA<SttException>()),
      );
    });

    test('setupUnavailable sets up unavailable stub', () async {
      mockService.setupUnavailable();

      final isAvailable = await mockService.isAvailable();

      expect(isAvailable, isFalse);
    });

    test('multiple stubs can be set up independently', () async {
      mockService.setupSuccessfulTranscription(text: '첫 번째');
      final first = await mockService.transcribe('/test/path1.wav');

      mockService.setupSuccessfulTranscription(text: '두 번째');
      final second = await mockService.transcribe('/test/path2.wav');

      expect(first.text, '첫 번째');
      expect(second.text, '두 번째');
    });
  });
}
