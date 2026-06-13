import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/transcription_result.dart';
import 'package:voice_to_textnote/providers/offline_stt_provider.dart';
import 'package:voice_to_textnote/services/offline_stt_service.dart';
import 'package:voice_to_textnote/mocks/mock_platform_stt_service.dart';

void main() {
  group('OfflineSttNotifier', () {
    late OfflineSttNotifier notifier;
    late MockPlatformSttService mockPlatformService;

    setUp(() {
      mockPlatformService = MockPlatformSttService();
      notifier = OfflineSttNotifier(OfflineSttService(mockPlatformService));
    });

    test('초기 상태는 idle', () {
      expect(notifier.state.status, equals(OfflineSttStatus.idle));
      expect(notifier.state.progress, equals(0.0));
    });

    test('변환 성공 시 completed 상태', () async {
      // Given: mock 설정
      when(() => mockPlatformService.transcribe(any()))
          .thenAnswer((_) async => TranscriptionResult(
                text: 'Complete',
                segments: const [],
                language: 'en',
                offline: false,
                createdAt: DateTime.now(),
                engineInfo: 'whisper-base',
              ));

      // When: 변환 실행
      await notifier.transcribe('/test/audio.wav');

      // Then: 완료 상태
      expect(notifier.state.status, equals(OfflineSttStatus.completed));
      expect(notifier.state.progress, equals(100.0));
      expect(notifier.state.result, isNotNull);
      expect(notifier.state.result!.text, equals('Complete'));
      expect(notifier.state.result!.offline, isTrue); // offline 플래그 추가 확인
      expect(notifier.state.error, isNull);
    });

    test('변환 실패 시 failed 상태', () async {
      // Given: mock 에러 설정
      when(() => mockPlatformService.transcribe(any()))
          .thenThrow(Exception('Processing failed'));

      // When: 변환 실행
      await notifier.transcribe('/test/audio.wav');

      // Then: 실패 상태
      expect(notifier.state.status, equals(OfflineSttStatus.failed));
      expect(notifier.state.error, contains('Processing failed'));
      expect(notifier.state.progress, greaterThanOrEqualTo(0.0));
    });

    test('진행률 Stream 노출', () async {
      // Given: mock 설정
      final progressValues = <double>[];
      notifier.stream.listen((state) {
        progressValues.add(state.progress);
      });

      when(() => mockPlatformService.transcribe(any()))
          .thenAnswer((_) async => TranscriptionResult(
                text: 'Complete',
                segments: const [],
                language: 'en',
                offline: false,
                createdAt: DateTime.now(),
                engineInfo: 'whisper-base',
              ));

      // When: 변환 실행
      await notifier.transcribe('/test/audio.wav');

      // Then: 진행률 확인 (preprocessing → completed)
      expect(progressValues, contains(0.0)); // preprocessing
      expect(progressValues.last, equals(100.0)); // completed
      expect(progressValues, everyElement(greaterThanOrEqualTo(0.0)));
      expect(progressValues, everyElement(lessThanOrEqualTo(100.0)));
    });

    test('상태 전이: idle → preprocessing → transcribing → completed', () async {
      // Given: 상태 변경 추적
      final stateChanges = <OfflineSttStatus>[];
      notifier.stream.listen((state) {
        stateChanges.add(state.status);
      });

      when(() => mockPlatformService.transcribe(any()))
          .thenAnswer((_) async => TranscriptionResult(
                text: 'Done',
                segments: const [],
                language: 'en',
                offline: false,
                createdAt: DateTime.now(),
                engineInfo: 'whisper-base',
              ));

      // When: 변환 실행
      await notifier.transcribe('/test/audio.wav');

      // Then: 상태 전이 확인
      expect(
        stateChanges,
        containsAll([
          OfflineSttStatus.processing, // preprocessing → transcribing
          OfflineSttStatus.completed,
        ]),
      );
    });
  });
}
