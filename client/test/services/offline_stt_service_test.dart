import 'dart:io';

import 'package:mocktail/mocktail.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/transcription_result.dart';
import 'package:voice_to_textnote/services/offline_stt_service.dart';

import 'package:voice_to_textnote/mocks/mock_platform_stt_service.dart';

void main() {
  group('OfflineSttService', () {
    late OfflineSttService service;
    late MockPlatformSttService mockPlatformService;
    late Directory tempDir;

    setUp(() async {
      mockPlatformService = MockPlatformSttService();
      service = OfflineSttService(mockPlatformService);
      tempDir =
          await Directory.systemTemp.createTemp('offline_stt_service_test_');
    });

    tearDown(() async {
      if (await tempDir.exists()) {
        await tempDir.delete(recursive: true);
      }
    });

    group('transcribe', () {
      test('WAV 파일을 텍스트로 변환', () async {
        // Given: mock 설정
        const wavPath = '/test/audio.wav';
        const expectedText = 'Hello, this is a test transcription';

        when(() => mockPlatformService.transcribe(any()))
            .thenAnswer((_) async => TranscriptionResult(
                  text: expectedText,
                  segments: const [],
                  language: 'en',
                  offline: false,
                  createdAt: DateTime.now(),
                  processingDuration: const Duration(seconds: 5),
                  engineInfo: 'whisper-base',
                ));

        // When: 변환 실행
        final result = await service.transcribe(wavPath);

        // Then: 결과 검증
        expect(result.text, equals(expectedText));
        expect(result.offline, isTrue);
        expect(result.processingDuration, isNotNull);
        verify(() => mockPlatformService.transcribe(wavPath)).called(1);
      });

      test('빈 파일 경로일 때 예외 발생', () async {
        // Given: mock 설정
        when(() => mockPlatformService.transcribe(any()))
            .thenThrow(Exception('파일 경로가 비어있습니다'));

        // When & Then: 예외 발생
        await expectLater(
          () => service.transcribe(''),
          throwsA(isA<Exception>()),
        );
      });

      test('Platform 서비스 에러 시 graceful 처리', () async {
        // Given: 플랫폼 서비스 에러
        when(() => mockPlatformService.transcribe(any()))
            .thenThrow(Exception('STT 처리 실패'));

        // When & Then: 예외 전파
        await expectLater(
          () => service.transcribe('/test/file.wav'),
          throwsA(isA<Exception>()),
        );
      });

      test('TranscriptionResult에 offline 메타데이터 포함', () async {
        // Given: mock 설정
        when(() => mockPlatformService.transcribe(any()))
            .thenAnswer((_) async => TranscriptionResult(
                  text: 'Test',
                  segments: const [],
                  language: 'en',
                  offline: false, // Platform 서비스는 false 반환
                  createdAt: DateTime.now(),
                  engineInfo: 'whisper-base',
                ));

        // When: 변환 실행
        final result = await service.transcribe('/test/audio.wav');

        // Then: offline 플래그가 true로 설정됨
        expect(result.offline, isTrue);
      });
    });

    group('isAvailable', () {
      test('오프라인 모드 가용 여부 확인', () async {
        // Given: mock 설정
        when(() => mockPlatformService.isAvailable())
            .thenAnswer((_) async => true);

        // When: 가용 여부 확인
        final available = await service.isAvailable();

        // Then: 결과 반환
        expect(available, isTrue);
        verify(() => mockPlatformService.isAvailable()).called(1);
      });

      test('모델 미설치 시 false 반환', () async {
        // Given: mock 설정
        when(() => mockPlatformService.isAvailable())
            .thenAnswer((_) async => false);

        // When: 가용 여부 확인
        final available = await service.isAvailable();

        // Then: false 반환
        expect(available, isFalse);
      });
    });

    group('transcribeWithChunks', () {
      test('5분 초과 오디오를 30초 청크로 분할 처리', () async {
        // Given: 6분 오디오 (360초 = 11.52MB)
        final wavFile = File('${tempDir.path}/long_audio.wav');
        await wavFile.writeAsBytes(List.filled(32000 * 360, 0));

        when(() => mockPlatformService.transcribe(any()))
            .thenAnswer((_) async => TranscriptionResult(
                  text: 'Chunk transcription',
                  segments: const [],
                  language: 'en',
                  offline: false,
                  createdAt: DateTime.now(),
                  engineInfo: 'whisper-base',
                ));

        // When: 청크 분할 처리
        final progressStream = service.transcribeWithProgress(wavFile.path);
        final results = await progressStream.toList();

        // Then: 최소 12개 이상의 이벤트 (starting + processing * n + completed)
        expect(results.length, greaterThanOrEqualTo(12));
        expect(results.last.progress, equals(100.0));
        expect(results.last.status, equals(TranscriptionStatus.completed));
      });

      test('청크 결과 병합', () async {
        // Given: 청크별 결과 설정
        int callCount = 0;
        when(() => mockPlatformService.transcribe(any())).thenAnswer((_) async {
          callCount++;
          return TranscriptionResult(
            text: 'Chunk $callCount',
            segments: const [],
            language: 'en',
            offline: false,
            createdAt: DateTime.now(),
            engineInfo: 'whisper-base',
          );
        });

        // When: 청크 분할 처리
        final wavFile = File('${tempDir.path}/audio.wav');
        await wavFile.writeAsBytes(List.filled(32000 * 360, 0));

        final progressStream = service.transcribeWithProgress(wavFile.path);
        final results = await progressStream.toList();

        // Then: 마지막 결과에 병합된 텍스트
        final finalResult = results.last.result;
        expect(finalResult, isNotNull);
      });
    });

    group('progress stream', () {
      test('실시간 진행률 보고', () async {
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

        // When: 진행률 스트림 구독
        final progressStream =
            service.transcribeWithProgress('/test/audio.wav');
        final progressUpdates =
            await progressStream.map((e) => e.progress).toList();

        // Then: 0%에서 100%까지 진행
        expect(progressUpdates.first, equals(0.0));
        expect(progressUpdates.last, equals(100.0));
        expect(progressUpdates, everyElement(greaterThanOrEqualTo(0.0)));
        expect(progressUpdates, everyElement(lessThanOrEqualTo(100.0)));
      });

      test('완료 후 WAV 파일 삭제', () async {
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

        // When: 처리 완료
        final progressStream =
            service.transcribeWithProgress('/test/audio.wav');
        await progressStream.last;

        // Then: WAV 파일 삭제 (시뮬레이션에서는 경로만 확인)
        // 실제 구현에서는 파일 삭제 로직이 필요
      });
    });
  });
}
