// PipelineProvider 상태 관리 테스트
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/providers/pipeline_provider.dart';
import 'package:voice_to_textnote/services/diarization_api.dart';
import 'package:voice_to_textnote/services/health_api.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';
import 'package:voice_to_textnote/services/transcription_api.dart';

// Mock 클래스 정의
class MockTranscriptionApi extends Mock implements TranscriptionApi {}

class MockDiarizationApi extends Mock implements DiarizationApi {}

class MockMinutesApi extends Mock implements MinutesApi {}

class MockSummaryApi extends Mock implements SummaryApi {}

class MockHealthApi extends Mock implements HealthApi {}

void main() {
  late MockTranscriptionApi mockSttApi;
  late MockDiarizationApi mockDiaApi;
  late MockMinutesApi mockMinApi;
  late MockSummaryApi mockSumApi;
  late ProviderContainer container;

  setUp(() {
    mockSttApi = MockTranscriptionApi();
    mockDiaApi = MockDiarizationApi();
    mockMinApi = MockMinutesApi();
    mockSumApi = MockSummaryApi();

    container = ProviderContainer(
      overrides: [
        transcriptionApiProvider.overrideWithValue(mockSttApi),
        diarizationApiProvider.overrideWithValue(mockDiaApi),
        minutesApiProvider.overrideWithValue(mockMinApi),
        summaryApiProvider.overrideWithValue(mockSumApi),
      ],
    );
  });

  tearDown(() {
    container.dispose();
  });

  group('PipelineProvider', () {
    // 초기 상태 테스트
    test('초기 상태는 idle이어야 함', () {
      final state = container.read(pipelineProvider);

      expect(state.currentStep, PipelineStep.idle);
      expect(state.progress, 0.0);
      expect(state.errorMessage, isNull);
    });

    // 파이프라인 성공 시나리오 테스트
    test('startPipeline이 성공 시 completed 상태로 진행해야 함', () async {
      // Arrange: 모든 API 호출 모킹
      when(() => mockSttApi.upload(any()))
          .thenAnswer((_) async => {'task_id': 'stt-001'});

      when(() => mockSttApi.getStatus('stt-001'))
          .thenAnswer((_) async => {'status': 'completed'});

      when(() => mockSttApi.getResult('stt-001'))
          .thenAnswer((_) async => {'task_id': 'stt-001', 'text': '테스트 텍스트'});

      when(() => mockDiaApi.create('stt-001'))
          .thenAnswer((_) async => {'task_id': 'dia-001'});

      when(() => mockDiaApi.getStatus('dia-001'))
          .thenAnswer((_) async => {'status': 'completed'});

      when(() => mockDiaApi.getResult('dia-001'))
          .thenAnswer((_) async => {'task_id': 'dia-001', 'segments': []});

      when(() => mockMinApi.create('dia-001'))
          .thenAnswer((_) async => {'task_id': 'min-001'});

      when(() => mockMinApi.getStatus('min-001'))
          .thenAnswer((_) async => {'status': 'completed'});

      when(() => mockMinApi.getResult('min-001'))
          .thenAnswer((_) async => {'task_id': 'min-001', 'minutes': '회의록 내용'});

      when(() => mockSumApi.create('min-001'))
          .thenAnswer((_) async => {'task_id': 'sum-001'});

      when(() => mockSumApi.getStatus('sum-001'))
          .thenAnswer((_) async => {'status': 'completed'});

      when(() => mockSumApi.getResult('sum-001')).thenAnswer(
          (_) async => {'task_id': 'sum-001', 'summary': 'AI 요약 내용'});

      // Act
      await container
          .read(pipelineProvider.notifier)
          .startPipeline('/tmp/test.m4a');

      // Assert
      final state = container.read(pipelineProvider);
      expect(state.currentStep, PipelineStep.completed);
      expect(state.progress, 1.0);
    });

    // 파이프라인 실패 시나리오 테스트
    test('startPipeline이 업로드 실패 시 failed 상태로 변경해야 함', () async {
      // Arrange: 업로드 실패 모킹
      when(() => mockSttApi.upload(any())).thenThrow(DioException(
        requestOptions: RequestOptions(path: ''),
        message: '업로드 실패',
      ));

      // Act
      await container
          .read(pipelineProvider.notifier)
          .startPipeline('/tmp/test.m4a');

      // Assert
      final state = container.read(pipelineProvider);
      expect(state.currentStep, PipelineStep.failed);
      expect(state.errorMessage, isNotNull);
    });
  });
}
