import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/transcription_result.dart';
import 'package:voice_to_textnote/services/platform_stt_service.dart';

/// PlatformSttService Mock 클래스
class MockPlatformSttService extends Mock implements PlatformSttService {}

/// MockPlatformSttService를 위한 헬퍼 익스텐션
extension MockPlatformSttServiceHelpers on MockPlatformSttService {
  /// 성공적인 전사 결과 stub 설정
  void setupSuccessfulTranscription({
    String text = '테스트 전사 결과',
    bool offline = true,
  }) {
    final result = offline
        ? TranscriptionResult.offline(
            text: text,
            segments: [
              TranscriptionSegment(
                startTime: Duration(seconds: 0),
                endTime: Duration(seconds: 5),
                text: text,
              ),
            ],
            language: 'ko',
            createdAt: DateTime.now(),
            processingDuration: const Duration(seconds: 3),
          )
        : TranscriptionResult.online(
            text: text,
            segments: [
              TranscriptionSegment(
                startTime: Duration(seconds: 0),
                endTime: Duration(seconds: 5),
                text: text,
              ),
            ],
            language: 'ko',
            createdAt: DateTime.now(),
            processingDuration: const Duration(seconds: 2),
          );

    when(() => transcribe(any(), language: any(named: 'language')))
        .thenAnswer((_) async => result);
  }

  /// 실패 stub 설정
  void setupFailure(String message) {
    when(() => transcribe(any(), language: any(named: 'language')))
        .thenThrow(SttException(message, code: 'MOCK_ERROR'));
  }

  /// 사용 불가 상태 stub 설정
  void setupUnavailable() {
    when(() => isAvailable()).thenAnswer((_) async => false);
  }

  /// 사용 가능 상태 stub 설정
  void setupAvailable() {
    when(() => isAvailable()).thenAnswer((_) async => true);
  }

  /// 엔진 정보 stub 설정
  void setupEngineInfo({
    String name = 'whisper.cpp',
    String platform = 'ios',
    String? accelerator = 'coreml',
    String modelVersion = 'whisper-base',
  }) {
    when(() => getEngineInfo()).thenAnswer(
      (_) async => EngineInfo(
        name: name,
        platform: platform,
        accelerator: accelerator,
        modelVersion: modelVersion,
      ),
    );
  }
}
