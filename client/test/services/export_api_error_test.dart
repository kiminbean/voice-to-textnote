// ExportApi 에러 처리 테스트 - SPEC-EXPORT-001 Phase 3
// 네트워크 에러 및 HTTP 에러 응답 처리 검증
import 'package:dio/dio.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/export_api.dart';

class MockDio extends Mock implements Dio {}

void main() {
  // Flutter 바인딩 초기화 (path_provider 플러그인 채널 등록에 필요)
  TestWidgetsFlutterBinding.ensureInitialized();

  late MockDio mockDio;
  late ExportApi exportApi;

  setUp(() {
    mockDio = MockDio();
    exportApi = ExportApi(mockDio);

    // path_provider 플랫폼 채널을 테스트용 임시 경로로 mock 처리
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'),
      (MethodCall methodCall) async {
        if (methodCall.method == 'getTemporaryDirectory') {
          return '/tmp/test_temp';
        }
        return null;
      },
    );
  });

  tearDown(() {
    // 채널 mock 해제
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'),
      null,
    );
  });

  group('ExportApi - 에러 처리', () {
    // test_download_pdf_network_error:
    // 네트워크 에러 시 DioException이 외부로 전파되어야 함
    test('네트워크 에러 발생 시 DioException을 전파해야 함', () async {
      // Arrange: Dio가 connectionError를 던지도록 설정
      when(
        () => mockDio.download(
          any(),
          any(),
          queryParameters: any(named: 'queryParameters'),
        ),
      ).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/export/pdf/min-001'),
          type: DioExceptionType.connectionError,
          message: '네트워크 연결 오류',
        ),
      );

      // Act & Assert: DioException이 발생해야 함
      expect(
        () async => exportApi.downloadPdf('min-001'),
        throwsA(isA<DioException>()),
      );
    });

    // test_download_pdf_404_error:
    // 404 응답 시 DioException이 외부로 전파되어야 함
    test('404 응답 시 DioException을 전파해야 함', () async {
      // Arrange: Dio가 badResponse (404)를 던지도록 설정
      when(
        () => mockDio.download(
          any(),
          any(),
          queryParameters: any(named: 'queryParameters'),
        ),
      ).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/export/pdf/nonexistent'),
          type: DioExceptionType.badResponse,
          response: Response(
            requestOptions: RequestOptions(path: '/export/pdf/nonexistent'),
            statusCode: 404,
            statusMessage: 'Not Found',
          ),
        ),
      );

      // Act & Assert: DioException이 발생해야 함
      expect(
        () async => exportApi.downloadPdf('nonexistent'),
        throwsA(isA<DioException>()),
      );
    });

    // 404 에러의 상태 코드가 404인지 확인
    test('404 에러 응답의 상태 코드는 404이어야 함', () async {
      // Arrange
      final notFoundError = DioException(
        requestOptions: RequestOptions(path: '/export/pdf/nonexistent'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/export/pdf/nonexistent'),
          statusCode: 404,
          statusMessage: 'Not Found',
        ),
      );

      when(
        () => mockDio.download(
          any(),
          any(),
          queryParameters: any(named: 'queryParameters'),
        ),
      ).thenThrow(notFoundError);

      // Act & Assert: 에러의 응답 상태 코드 확인
      try {
        await exportApi.downloadPdf('nonexistent');
        fail('DioException이 발생해야 합니다');
      } on DioException catch (e) {
        expect(e.response?.statusCode, equals(404));
      }
    });

    // 연결 타임아웃 에러 처리
    test('연결 타임아웃 에러 시 DioException을 전파해야 함', () async {
      // Arrange
      when(
        () => mockDio.download(
          any(),
          any(),
          queryParameters: any(named: 'queryParameters'),
        ),
      ).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/export/pdf/min-001'),
          type: DioExceptionType.connectionTimeout,
          message: '연결 타임아웃',
        ),
      );

      // Act & Assert
      expect(
        () async => exportApi.downloadPdf('min-001'),
        throwsA(isA<DioException>()),
      );
    });
  });
}
