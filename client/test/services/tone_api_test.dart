// ToneApi 서비스 테스트 - SPEC-TONE-001 REQ-TONE-012/013
// @MX:SPEC: SPEC-TONE-001
// 패턴 매칭: minutes_api_test.dart (mocktail + MockDio)
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/tone_api.dart';

// Dio Mock 클래스 (minutes_api_test.dart 패턴 매칭)
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late ToneApi toneApi;

  setUp(() {
    mockDio = MockDio();
    toneApi = ToneApi(mockDio);
    // mocktail fallback 등록 (any() 사용 시 필요)
    registerFallbackValue(RequestOptions(path: ''));
  });

  group('ToneApi.getToneResult', () {
    // REQ-TONE-012: 성공 시 ToneResponse 파싱
    test('성공: ToneResponse를 올바르게 파싱하여 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'task_id': 'tone-001',
            'status': 'completed',
            'segments': [
              {
                'start': 0.0,
                'end': 2.5,
                'speaker': 'SPEAKER_00',
                'tone': 'calm',
                'confidence': 0.82,
                'prosody_features': {
                  'f0_mean': 120.5,
                  'f0_std': 15.3,
                  'rms_energy': 0.045,
                  'speaking_rate': 3.2,
                },
              },
            ],
            'speakers': [
              {
                'speaker': 'SPEAKER_00',
                'dominant_tone': 'calm',
                'tone_distribution': {'calm': 5, 'excited': 2},
                'avg_pitch': 118.3,
                'avg_energy': 0.042,
              },
            ],
            'overall_tone': 'calm',
            'error_message': null,
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await toneApi.getToneResult('tone-001');

      // Assert
      expect(result.taskId, 'tone-001');
      expect(result.status, 'completed');
      expect(result.segments, hasLength(1));
      expect(result.segments.first.tone, 'calm');
      expect(result.segments.first.confidence, 0.82);
      expect(result.segments.first.prosodyFeatures['f0_mean'], 120.5);
      expect(result.speakers, hasLength(1));
      expect(result.speakers.first.dominantTone, 'calm');
      expect(result.speakers.first.toneDistribution['calm'], 5.0);
      expect(result.overallTone, 'calm');
      expect(result.errorMessage, isNull);
      verify(() => mockDio.get('/tone/tone-001')).called(1);
    });

    // REQ-TONE-013: 404 시 silent return 금지, 명시적 예외 throw
    test('404: ToneNotFoundException을 throw해야 함 (null/빈 반환 금지)',
        () async {
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          response: Response(
            statusCode: 404,
            requestOptions: RequestOptions(path: ''),
          ),
          type: DioExceptionType.badResponse,
        ),
      );

      expect(
        () => toneApi.getToneResult('not-found'),
        throwsA(isA<ToneNotFoundException>()),
      );
    });

    // REQ-TONE-013: 503 시 기능 비활성화 예외
    test('503: ToneDisabledException을 throw해야 함 (톤 분석 비활성화)', () async {
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          response: Response(
            statusCode: 503,
            requestOptions: RequestOptions(path: ''),
          ),
          type: DioExceptionType.badResponse,
        ),
      );

      expect(
        () => toneApi.getToneResult('disabled'),
        throwsA(isA<ToneDisabledException>()),
      );
    });

    // REQ-TONE-013: 기타 오류도 예외 전파 (null 반환 금지)
    test('기타 네트워크 오류: ToneApiException을 throw해야 함', () async {
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.connectionTimeout,
          message: '연결 시간 초과',
        ),
      );

      expect(
        () => toneApi.getToneResult('any'),
        throwsA(isA<ToneApiException>()),
      );
    });
  });

  group('ToneApi.getToneByMeeting', () {
    // REQ-TONE-012: meetingId 기반 조회 성공
    test('성공: ToneResponse를 파싱하여 반환해야 함', () async {
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'task_id': 'tone-002',
            'status': 'completed',
            'segments': [],
            'speakers': [],
            'overall_tone': 'unknown',
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await toneApi.getToneByMeeting('meeting-001');

      expect(result.taskId, 'tone-002');
      verify(() => mockDio.get('/tone/meeting/meeting-001')).called(1);
    });

    test('404: ToneNotFoundException을 throw해야 함', () async {
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          response: Response(
            statusCode: 404,
            requestOptions: RequestOptions(path: ''),
          ),
          type: DioExceptionType.badResponse,
        ),
      );

      expect(
        () => toneApi.getToneByMeeting('not-found'),
        throwsA(isA<ToneNotFoundException>()),
      );
    });
  });

  // REQ-TONE-013 핵심 검증: silent fallback 절대 금지
  // SPEC-SENTIMENT-001의 SizedBox.shrink() 버그 반복 방지
  group('REQ-TONE-013 silent fallback 방지', () {
    test('getToneResult는 어떤 오류에서도 null을 반환하지 않고 예외를 throw해야 함',
        () async {
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          response: Response(
            statusCode: 500,
            requestOptions: RequestOptions(path: ''),
          ),
          type: DioExceptionType.badResponse,
        ),
      );

      // 예외가 throw되어야 함 (null이나 빈 응답 반환 X)
      Object? result;
      ToneApiException? thrownException;
      try {
        result = await toneApi.getToneResult('any');
      } on ToneApiException catch (e) {
        thrownException = e;
      }

      expect(thrownException, isNotNull,
          reason: 'ToneApiException이 throw되어야 함');
      expect(result, isNull,
          reason: '정상 반환값이 없어야 함 (예외로만 종료)');
    });

    test('getToneByMeeting는 어떤 오류에서도 null을 반환하지 않고 예외를 throw해야 함',
        () async {
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.connectionError,
          message: '네트워크 오류',
        ),
      );

      expect(
        () => toneApi.getToneByMeeting('any'),
        throwsA(isA<ToneApiException>()),
      );
    });
  });
}
