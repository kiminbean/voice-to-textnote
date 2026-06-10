import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/offline_task.dart';
import 'package:voice_to_textnote/models/transcription_result.dart';
import 'package:voice_to_textnote/services/audio_preprocessor.dart';
import 'package:voice_to_textnote/services/connectivity_service.dart';
import 'package:voice_to_textnote/services/hybrid_pipeline_service.dart';
import 'package:voice_to_textnote/services/offline_stt_service.dart';

class MockAudioPreprocessor extends Mock implements AudioPreprocessor {}

class MockOfflineSttService extends Mock implements OfflineSttService {}

class MockConnectivityService extends Mock implements ConnectivityService {}

void main() {
  group('HybridPipelineService', () {
    late MockConnectivityService connectivityService;
    late MockAudioPreprocessor audioPreprocessor;
    late MockOfflineSttService offlineSttService;
    late HybridPipelineService service;
    late Directory tempDir;

    setUp(() async {
      connectivityService = MockConnectivityService();
      audioPreprocessor = MockAudioPreprocessor();
      offlineSttService = MockOfflineSttService();
      tempDir = await Directory.systemTemp.createTemp('hybrid_pipeline_test_');
      service = HybridPipelineService(
        connectivityService: connectivityService,
        audioPreprocessor: audioPreprocessor,
        offlineSttService: offlineSttService,
      );
    });

    tearDown(() async {
      service.dispose();
      if (await tempDir.exists()) {
        await tempDir.delete(recursive: true);
      }
    });

    test('연결 상태가 온라인이면 isOnline이 true', () {
      when(() => connectivityService.isOnline).thenReturn(true);

      expect(service.isOnline, isTrue);
    });

    test('오프라인 처리 결과를 pending 재처리 작업으로 등록', () async {
      final wavFile = File('${tempDir.path}/audio.wav');
      await wavFile.writeAsBytes([1, 2, 3]);
      when(() => audioPreprocessor.convertToWav(any()))
          .thenAnswer((_) async => wavFile);
      when(() => offlineSttService.transcribeWithProgress(wavFile.path))
          .thenAnswer(
        (_) => Stream.value(
          TranscriptionProgress(
            progress: 100,
            status: TranscriptionStatus.completed,
            result: TranscriptionResult.offline(
              text: '오프라인 전사',
              segments: const [],
              language: 'ko',
            ),
          ),
        ),
      );

      final result = await service.processOffline('/tmp/audio.m4a');

      expect(result.transcription.offline, isTrue);
      expect(result.transcription.text, '오프라인 전사');
      expect(service.pendingTasks, hasLength(1));
      expect(service.pendingTasks.single.status, OfflineTaskStatus.pending);
    });

    test('네트워크 복구 시 pending 작업을 완료 상태로 전환', () async {
      final wavFile = File('${tempDir.path}/audio.wav');
      await wavFile.writeAsBytes([1, 2, 3]);
      when(() => audioPreprocessor.convertToWav(any()))
          .thenAnswer((_) async => wavFile);
      when(() => offlineSttService.transcribeWithProgress(wavFile.path))
          .thenAnswer(
        (_) => Stream.value(
          TranscriptionProgress(
            progress: 100,
            status: TranscriptionStatus.completed,
            result: TranscriptionResult.offline(
              text: '오프라인 전사',
              segments: const [],
              language: 'ko',
            ),
          ),
        ),
      );
      await service.processOffline('/tmp/audio.m4a');

      final updated = await service.reprocessPendingTasks(
        (_) async => 'online-001',
      );

      expect(updated.single.status, OfflineTaskStatus.completed);
      expect(updated.single.onlineTranscriptionTaskId, 'online-001');
      expect(service.pendingTasks, isEmpty);
    });

    test('재처리 실패 시 failed 작업으로 보존', () async {
      final wavFile = File('${tempDir.path}/audio.wav');
      await wavFile.writeAsBytes([1, 2, 3]);
      when(() => audioPreprocessor.convertToWav(any()))
          .thenAnswer((_) async => wavFile);
      when(() => offlineSttService.transcribeWithProgress(wavFile.path))
          .thenAnswer(
        (_) => Stream.value(
          TranscriptionProgress(
            progress: 100,
            status: TranscriptionStatus.completed,
            result: TranscriptionResult.offline(
              text: '오프라인 전사',
              segments: const [],
              language: 'ko',
            ),
          ),
        ),
      );
      await service.processOffline('/tmp/audio.m4a');

      final updated = await service.reprocessPendingTasks(
        (_) async => throw DioException(
          requestOptions: RequestOptions(path: '/transcriptions'),
          message: 'upload failed',
        ),
      );

      expect(updated.single.status, OfflineTaskStatus.failed);
      expect(service.failedTasks, hasLength(1));
    });
  });
}
