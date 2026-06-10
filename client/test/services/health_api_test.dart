// HealthApi 서비스 테스트
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/health_api.dart';

// Dio Mock 클래스
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late HealthApi healthApi;

  setUp(() {
    mockDio = MockDio();
    healthApi = HealthApi(mockDio);
  });

  group('HealthApi', () {
    // 헬스체크 성공 테스트
    test('check가 서버 정상 시 true를 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer((_) async => Response(
            data: {'status': 'healthy'},
            statusCode: 200,
            requestOptions: RequestOptions(path: ''),
          ));

      // Act
      final result = await healthApi.check();

      // Assert
      expect(result, isTrue);
    });

    // 헬스체크 실패 테스트
    test('check가 서버 오류 시 false를 반환해야 함', () async {
      // Arrange: 네트워크 오류 시뮬레이션
      when(() => mockDio.get(any())).thenThrow(DioException(
        requestOptions: RequestOptions(path: ''),
        message: '연결 거부',
      ));

      // Act
      final result = await healthApi.check();

      // Assert
      expect(result, isFalse);
    });

    // 500 에러 시 false 반환 테스트
    test('check가 500 응답 시 false를 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer((_) async => Response(
            data: {'status': 'error'},
            statusCode: 500,
            requestOptions: RequestOptions(path: ''),
          ));

      // Act
      final result = await healthApi.check();

      // Assert
      expect(result, isFalse);
    });
  });
}
