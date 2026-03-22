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
      expect(() => diarizationApi.getResult('dia-001'), throwsA(isA<DioException>()));
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
      expect(() => diarizationApi.getResult('dia-001'), throwsA(isA<DioException>()));
    });
  });
}
