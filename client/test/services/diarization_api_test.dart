// DiarizationApi 서비스 테스트 - SPEC-APP-004 REQ-APP-044
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/diarization_api.dart';

// Dio Mock 클래스
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late DiarizationApi diarizationApi;

  setUp(() {
    mockDio = MockDio();
    diarizationApi = DiarizationApi(mockDio);
  });

  group('DiarizationApi', () {
    test('create가 화자 수 힌트를 요청 바디에 포함해야 함', () async {
      when(() => mockDio.post(any(), data: any(named: 'data'))).thenAnswer(
        (_) async => Response(
          data: {'task_id': 'dia-001'},
          statusCode: 201,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await diarizationApi.create(
        'stt-001',
        minSpeakers: 2,
        maxSpeakers: 8,
      );

      expect(result['task_id'], 'dia-001');
      final captured = verify(
        () => mockDio.post(captureAny(), data: captureAny(named: 'data')),
      ).captured;
      expect(captured[0], '/diarizations');
      expect(captured[1], {
        'stt_task_id': 'stt-001',
        'min_speakers': 2,
        'max_speakers': 8,
      });
    });

    // getResult: 화자 분리 결과 조회 성공 테스트
    test('getResult가 화자 분리 결과를 올바르게 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'segments': [
              {
                'speaker': 'SPEAKER_00',
                'speaker_name': '화자 1',
                'start': 0.0,
                'end': 3.5,
                'text': '회의를 시작하겠습니다.',
              },
              {
                'speaker': 'SPEAKER_01',
                'speaker_name': '화자 2',
                'start': 4.0,
                'end': 7.2,
                'text': '네, 시작하시죠.',
              },
            ],
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await diarizationApi.getResult('dia-001');

      // Assert
      expect(result['segments'], hasLength(2));
      expect(result['segments'][0]['speaker_name'], '화자 1');
      expect(result['segments'][1]['text'], '네, 시작하시죠.');
      // diarization getResult는 /result 경로 사용
      verify(() => mockDio.get('/diarizations/dia-001/result')).called(1);
    });

    // getResult: 네트워크 오류 시 예외 전파 테스트
    test('getResult가 네트워크 오류 시 DioException을 전파해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          message: '연결 오류',
        ),
      );

      // Act & Assert
      expect(() => diarizationApi.getResult('dia-001'),
          throwsA(isA<DioException>()));
    });

    // getResult: 500 오류 시 예외 전파 테스트
    test('getResult가 서버 오류 시 DioException을 전파해야 함', () async {
      // Arrange
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

      // Act & Assert
      expect(() => diarizationApi.getResult('dia-001'),
          throwsA(isA<DioException>()));
    });
  });
}
