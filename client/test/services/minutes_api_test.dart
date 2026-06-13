// MinutesApi 서비스 테스트 - SPEC-APP-004 REQ-APP-044
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';

// Dio Mock 클래스
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late MinutesApi minutesApi;

  setUp(() {
    mockDio = MockDio();
    minutesApi = MinutesApi(mockDio);
  });

  group('MinutesApi', () {
    // getResult: 회의록 결과 조회 성공 테스트 (markdown 포함)
    test('getResult가 markdown 필드를 포함한 회의록 결과를 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'markdown': '# 회의록\n\n## 참석자\n- 김철수\n- 이영희',
            'segments': [],
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await minutesApi.getResult('min-001');

      // Assert
      expect(result['markdown'], contains('# 회의록'));
      verify(() => mockDio.get('/minutes/min-001')).called(1);
    });

    // getResult: segments 형식으로 반환하는 경우 테스트
    test('getResult가 segments 배열을 포함한 결과를 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'segments': [
              {'speaker_name': '김철수', 'text': '안녕하세요.'},
              {'speaker_name': '이영희', 'text': '반갑습니다.'},
            ],
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await minutesApi.getResult('min-002');

      // Assert
      expect(result['segments'], hasLength(2));
      verify(() => mockDio.get('/minutes/min-002')).called(1);
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
      expect(
          () => minutesApi.getResult('min-001'), throwsA(isA<DioException>()));
    });
  });
}
