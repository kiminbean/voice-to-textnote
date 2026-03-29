// HistoryApi 서비스 테스트 - SPEC-HISTSYNC-001 REQ-HSYNC-001
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/history_api.dart';

// Dio Mock 클래스
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late HistoryApi historyApi;

  setUp(() {
    mockDio = MockDio();
    historyApi = HistoryApi(mockDio);
  });

  group('HistoryApi', () {
    // list: 기본 호출 성공 테스트
    test('list가 서버 이력 목록을 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenAnswer(
        (_) async => Response(
          data: {
            'items': [
              {
                'task_id': 'sum-001',
                'task_type': 'summary',
                'status': 'completed',
                'created_at': '2024-01-15T10:00:00Z',
                'completed_at': '2024-01-15T10:05:00Z',
              }
            ],
            'total': 1,
            'page': 1,
            'page_size': 20,
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await historyApi.list();

      // Assert
      expect(result['items'], hasLength(1));
      expect(result['total'], 1);
      expect(result['items'][0]['task_id'], 'sum-001');
      verify(() => mockDio.get(
            '/history',
            queryParameters: any(named: 'queryParameters'),
          )).called(1);
    });

    // list: task_type, status 파라미터 전달 테스트
    test('list가 task_type=summary, status=completed 파라미터를 올바르게 전달해야 함',
        () async {
      // Arrange
      when(() => mockDio.get(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenAnswer(
        (_) async => Response(
          data: {'items': [], 'total': 0, 'page': 1, 'page_size': 20},
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      await historyApi.list(taskType: 'summary', status: 'completed');

      // Assert: 올바른 쿼리 파라미터로 호출되었는지 검증
      verify(() => mockDio.get(
            '/history',
            queryParameters: {
              'task_type': 'summary',
              'status': 'completed',
              'page': 1,
              'page_size': 20,
            },
          )).called(1);
    });

    // list: 페이지네이션 파라미터 테스트
    test('list가 page, page_size 파라미터를 전달해야 함', () async {
      // Arrange
      when(() => mockDio.get(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenAnswer(
        (_) async => Response(
          data: {'items': [], 'total': 0, 'page': 2, 'page_size': 10},
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      await historyApi.list(page: 2, pageSize: 10);

      // Assert
      verify(() => mockDio.get(
            '/history',
            queryParameters: {
              'page': 2,
              'page_size': 10,
            },
          )).called(1);
    });

    // list: 네트워크 오류 시 예외 전파 테스트
    test('list가 네트워크 오류 시 DioException을 전파해야 함', () async {
      // Arrange
      when(() => mockDio.get(
            any(),
            queryParameters: any(named: 'queryParameters'),
          )).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          message: '네트워크 연결 오류',
        ),
      );

      // Act & Assert
      expect(
        () => historyApi.list(),
        throwsA(isA<DioException>()),
      );
    });

    // get: 단건 이력 상세 조회 성공 테스트
    test('get이 task_id로 이력 상세 정보를 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'task_id': 'sum-001',
            'task_type': 'summary',
            'status': 'completed',
            'created_at': '2024-01-15T10:00:00Z',
            'result_data': {'summary_text': '요약 내용'},
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await historyApi.get('sum-001');

      // Assert
      expect(result['task_id'], 'sum-001');
      expect(result['result_data'], isNotNull);
      verify(() => mockDio.get('/history/sum-001')).called(1);
    });

    // get: 존재하지 않는 task_id 시 404 예외 테스트
    test('get이 존재하지 않는 task_id로 요청 시 DioException을 전파해야 함', () async {
      // Arrange
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

      // Act & Assert
      expect(
        () => historyApi.get('unknown-id'),
        throwsA(isA<DioException>()),
      );
    });

    // delete: 이력 삭제 성공 테스트
    test('delete가 task_id로 이력을 삭제해야 함', () async {
      // Arrange
      when(() => mockDio.delete(any())).thenAnswer(
        (_) async => Response(
          data: null,
          statusCode: 204,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      await historyApi.delete('sum-001');

      // Assert: 예외 없이 완료
      verify(() => mockDio.delete('/history/sum-001')).called(1);
    });

    // delete: 존재하지 않는 task_id 시 404 예외 테스트
    test('delete가 존재하지 않는 task_id 시 DioException을 전파해야 함', () async {
      // Arrange
      when(() => mockDio.delete(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          response: Response(
            statusCode: 404,
            requestOptions: RequestOptions(path: ''),
          ),
          type: DioExceptionType.badResponse,
        ),
      );

      // Act & Assert
      expect(
        () => historyApi.delete('unknown-id'),
        throwsA(isA<DioException>()),
      );
    });
  });
}
