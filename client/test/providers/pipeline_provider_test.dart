// PipelineProvider 상태 관리 테스트
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/auth_user.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/providers/pipeline_provider.dart';
import 'package:voice_to_textnote/services/auth_api.dart';
import 'package:voice_to_textnote/services/auth_service.dart';
import 'package:voice_to_textnote/services/diarization_api.dart';
import 'package:voice_to_textnote/services/health_api.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/sse_service.dart';
import 'package:voice_to_textnote/services/summary_api.dart';
import 'package:voice_to_textnote/services/transcription_api.dart';

// Mock 클래스 정의
class MockTranscriptionApi extends Mock implements TranscriptionApi {}

class MockDiarizationApi extends Mock implements DiarizationApi {}

class MockMinutesApi extends Mock implements MinutesApi {}

class MockSummaryApi extends Mock implements SummaryApi {}

class MockHealthApi extends Mock implements HealthApi {}

class MockSseService extends Mock implements SseService {}

class MockAuthApi extends Mock implements AuthApi {}

class MockAuthService extends Mock implements AuthService {}

void main() {
  late MockTranscriptionApi mockSttApi;
  late MockDiarizationApi mockDiaApi;
  late MockMinutesApi mockMinApi;
  late MockSummaryApi mockSumApi;
  late MockSseService mockSseService;
  late MockAuthApi mockAuthApi;
  late MockAuthService mockAuthService;
  late ProviderContainer container;

  setUp(() {
    mockSttApi = MockTranscriptionApi();
    mockDiaApi = MockDiarizationApi();
    mockMinApi = MockMinutesApi();
    mockSumApi = MockSummaryApi();
    mockSseService = MockSseService();
    mockAuthApi = MockAuthApi();
    mockAuthService = MockAuthService();

    when(() => mockSseService.connect(any()))
        .thenAnswer((_) => const Stream<Map<String, dynamic>>.empty());
    when(() => mockSseService.disconnect()).thenReturn(null);
    when(() => mockAuthService.getAccessToken()).thenAnswer((_) async => null);
    when(() => mockAuthService.isAccessTokenExpired())
        .thenAnswer((_) async => true);
    when(() => mockAuthService.getRefreshToken()).thenAnswer((_) async => null);
    when(() => mockAuthService.clearTokens()).thenAnswer((_) async {});
    when(() => mockAuthService.clearGuestSession()).thenAnswer((_) async {});
    when(() => mockAuthService.saveTokens(any(), any()))
        .thenAnswer((_) async {});
    when(() => mockAuthApi.createGuestSession()).thenAnswer(
      (_) async => {
        'guest_session_id': 'guest-session-001',
        'guest_token': 'guest-token-001',
      },
    );
    when(
      () => mockAuthService.saveGuestToken(
        'guest-token-001',
        'guest-session-001',
      ),
    ).thenAnswer((_) async {});

    container = ProviderContainer(
      overrides: [
        transcriptionApiProvider.overrideWithValue(mockSttApi),
        diarizationApiProvider.overrideWithValue(mockDiaApi),
        minutesApiProvider.overrideWithValue(mockMinApi),
        summaryApiProvider.overrideWithValue(mockSumApi),
        sseServiceProvider.overrideWithValue(mockSseService),
        authApiProvider.overrideWithValue(mockAuthApi),
        authServiceProvider.overrideWithValue(mockAuthService),
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

    test('API key와 저장 토큰이 없으면 게스트 세션 생성 후 업로드해야 함', () async {
      when(() => mockSttApi.upload(any()))
          .thenAnswer((_) async => {'task_id': 'stt-001'});
      when(() => mockSttApi.getStatus('stt-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockDiaApi.create('stt-001'))
          .thenAnswer((_) async => {'task_id': 'dia-001'});
      when(() => mockDiaApi.getStatus('dia-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockMinApi.create('dia-001'))
          .thenAnswer((_) async => {'task_id': 'min-001'});
      when(() => mockMinApi.getStatus('min-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockSumApi.create('min-001'))
          .thenAnswer((_) async => {'task_id': 'sum-001'});
      when(() => mockSumApi.getStatus('sum-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );

      await container
          .read(pipelineProvider.notifier)
          .startPipeline('/tmp/test.m4a');

      verifyInOrder([
        () => mockAuthService.getAccessToken(),
        () => mockAuthService.getRefreshToken(),
        () => mockAuthApi.createGuestSession(),
        () => mockAuthService.clearGuestSession(),
        () => mockAuthService.saveGuestToken(
              'guest-token-001',
              'guest-session-001',
            ),
        () => mockSttApi.upload('/tmp/test.m4a'),
      ]);
    });

    test('유효한 액세스 토큰이 있으면 게스트 세션을 만들지 않아야 함', () async {
      when(() => mockAuthService.getAccessToken())
          .thenAnswer((_) async => 'access-token');
      when(() => mockAuthService.isAccessTokenExpired())
          .thenAnswer((_) async => false);
      when(() => mockSttApi.upload(any()))
          .thenAnswer((_) async => {'task_id': 'stt-001'});
      when(() => mockSttApi.getStatus('stt-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockDiaApi.create('stt-001'))
          .thenAnswer((_) async => {'task_id': 'dia-001'});
      when(() => mockDiaApi.getStatus('dia-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockMinApi.create('dia-001'))
          .thenAnswer((_) async => {'task_id': 'min-001'});
      when(() => mockMinApi.getStatus('min-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockSumApi.create('min-001'))
          .thenAnswer((_) async => {'task_id': 'sum-001'});
      when(() => mockSumApi.getStatus('sum-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );

      await container
          .read(pipelineProvider.notifier)
          .startPipeline('/tmp/test.m4a');

      verifyNever(() => mockAuthApi.createGuestSession());
      verify(() => mockSttApi.upload('/tmp/test.m4a')).called(1);
    });

    test('만료된 액세스 토큰과 리프레시 토큰이 있으면 갱신 후 업로드해야 함', () async {
      when(() => mockAuthService.getAccessToken())
          .thenAnswer((_) async => 'expired-access-token');
      when(() => mockAuthService.isAccessTokenExpired())
          .thenAnswer((_) async => true);
      when(() => mockAuthService.getRefreshToken())
          .thenAnswer((_) async => 'refresh-token');
      when(() => mockAuthApi.refresh('refresh-token')).thenAnswer(
        (_) async => const TokenResponse(
          accessToken: 'new-access-token',
          refreshToken: 'new-refresh-token',
          tokenType: 'bearer',
        ),
      );
      when(() => mockSttApi.upload(any()))
          .thenAnswer((_) async => {'task_id': 'stt-001'});
      when(() => mockSttApi.getStatus('stt-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockDiaApi.create('stt-001'))
          .thenAnswer((_) async => {'task_id': 'dia-001'});
      when(() => mockDiaApi.getStatus('dia-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockMinApi.create('dia-001'))
          .thenAnswer((_) async => {'task_id': 'min-001'});
      when(() => mockMinApi.getStatus('min-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockSumApi.create('min-001'))
          .thenAnswer((_) async => {'task_id': 'sum-001'});
      when(() => mockSumApi.getStatus('sum-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );

      await container
          .read(pipelineProvider.notifier)
          .startPipeline('/tmp/test.m4a');

      verifyInOrder([
        () => mockAuthService.getAccessToken(),
        () => mockAuthService.isAccessTokenExpired(),
        () => mockAuthService.getRefreshToken(),
        () => mockAuthApi.refresh('refresh-token'),
        () => mockAuthService.saveTokens(
              'new-access-token',
              'new-refresh-token',
            ),
        () => mockSttApi.upload('/tmp/test.m4a'),
      ]);
      verifyNever(() => mockAuthApi.createGuestSession());
    });

    test('리프레시 실패 시 토큰과 기존 게스트를 지우고 새 게스트로 업로드해야 함', () async {
      when(() => mockAuthService.getAccessToken())
          .thenAnswer((_) async => 'expired-access-token');
      when(() => mockAuthService.isAccessTokenExpired())
          .thenAnswer((_) async => true);
      when(() => mockAuthService.getRefreshToken())
          .thenAnswer((_) async => 'stale-refresh-token');
      when(() => mockAuthApi.refresh('stale-refresh-token')).thenThrow(
        DioException(requestOptions: RequestOptions(path: '/auth/refresh')),
      );
      when(() => mockSttApi.upload(any()))
          .thenAnswer((_) async => {'task_id': 'stt-001'});
      when(() => mockSttApi.getStatus('stt-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockDiaApi.create('stt-001'))
          .thenAnswer((_) async => {'task_id': 'dia-001'});
      when(() => mockDiaApi.getStatus('dia-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockMinApi.create('dia-001'))
          .thenAnswer((_) async => {'task_id': 'min-001'});
      when(() => mockMinApi.getStatus('min-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );
      when(() => mockSumApi.create('min-001'))
          .thenAnswer((_) async => {'task_id': 'sum-001'});
      when(() => mockSumApi.getStatus('sum-001')).thenAnswer(
        (_) async => {'status': 'completed'},
      );

      await container
          .read(pipelineProvider.notifier)
          .startPipeline('/tmp/test.m4a');

      verifyInOrder([
        () => mockAuthApi.refresh('stale-refresh-token'),
        () => mockAuthService.clearTokens(),
        () => mockAuthApi.createGuestSession(),
        () => mockAuthService.clearGuestSession(),
        () => mockAuthService.saveGuestToken(
              'guest-token-001',
              'guest-session-001',
            ),
        () => mockSttApi.upload('/tmp/test.m4a'),
      ]);
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
