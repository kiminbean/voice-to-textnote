// ExportApi 서비스 단위 테스트 - SPEC-EXPORT-001
// path_provider는 플랫폼 채널 의존성이 있어 Dio 호출 검증 위주로 테스트
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

  group('ExportApi - 인스턴스 생성', () {
    test('ExportApi는 Dio 인스턴스로 생성되어야 함', () {
      // Assert: ExportApi가 정상적으로 생성됨
      expect(exportApi, isA<ExportApi>());
    });
  });

  group('ExportApi - downloadPdf 메서드', () {
    test('summaryTaskId 없으면 queryParameters를 null로 Dio.download 호출해야 함',
        () async {
      // Arrange: Dio download 성공 응답
      when(
        () => mockDio.download(
          any(),
          any(),
          queryParameters: null,
        ),
      ).thenAnswer((_) async => Response(
            requestOptions: RequestOptions(path: '/export/pdf/min-001'),
            statusCode: 200,
          ));

      // Act
      try {
        await exportApi.downloadPdf('min-001');
      } catch (_) {
        // 파일 시스템 접근 실패는 허용 (Dio 호출만 검증)
      }

      // Assert: queryParameters null로 호출되었는지 확인
      verify(
        () => mockDio.download(
          '/export/pdf/min-001',
          any(),
          queryParameters: null,
        ),
      ).called(1);
    });

    test('summaryTaskId가 있으면 summary_task_id를 queryParameters에 포함해야 함',
        () async {
      // Arrange
      when(
        () => mockDio.download(
          any(),
          any(),
          queryParameters: {'summary_task_id': 'sum-001'},
        ),
      ).thenAnswer((_) async => Response(
            requestOptions: RequestOptions(path: '/export/pdf/min-001'),
            statusCode: 200,
          ));

      // Act
      try {
        await exportApi.downloadPdf('min-001', summaryTaskId: 'sum-001');
      } catch (_) {
        // 파일 시스템 접근 실패는 허용
      }

      // Assert
      verify(
        () => mockDio.download(
          '/export/pdf/min-001',
          any(),
          queryParameters: {'summary_task_id': 'sum-001'},
        ),
      ).called(1);
    });

    test('minutesTaskId를 경로에 포함한 올바른 엔드포인트를 사용해야 함', () async {
      // Arrange
      const testTaskId = 'task-xyz-123';

      when(
        () => mockDio.download(
          any(),
          any(),
          queryParameters: any(named: 'queryParameters'),
        ),
      ).thenAnswer((_) async => Response(
            requestOptions: RequestOptions(path: '/export/pdf/$testTaskId'),
            statusCode: 200,
          ));

      // Act
      try {
        await exportApi.downloadPdf(testTaskId);
      } catch (_) {
        // 파일 시스템 접근 실패는 허용
      }

      // Assert: 경로에 minutesTaskId 포함
      verify(
        () => mockDio.download(
          '/export/pdf/$testTaskId',
          any(),
          queryParameters: any(named: 'queryParameters'),
        ),
      ).called(1);
    });

    test('파일 경로에 minutesTaskId가 포함된 파일명을 사용해야 함', () async {
      // Arrange
      const taskId = 'min-task-abc';

      when(
        () => mockDio.download(
          any(),
          any(that: contains('minutes_$taskId.pdf')),
          queryParameters: any(named: 'queryParameters'),
        ),
      ).thenAnswer((_) async => Response(
            requestOptions: RequestOptions(path: '/export/pdf/$taskId'),
            statusCode: 200,
          ));

      // Act
      try {
        await exportApi.downloadPdf(taskId);
      } catch (_) {
        // 파일 시스템 접근 실패는 허용
      }

      // Assert: 파일 경로에 올바른 파일명 포함
      verify(
        () => mockDio.download(
          any(),
          any(that: contains('minutes_$taskId.pdf')),
          queryParameters: any(named: 'queryParameters'),
        ),
      ).called(1);
    });
  });
}
