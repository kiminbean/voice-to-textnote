// SummaryApi 서비스 테스트 - SPEC-APP-004 REQ-APP-044
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/summary_api.dart';

// Dio Mock 클래스
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late SummaryApi summaryApi;

  setUp(() {
    mockDio = MockDio();
    summaryApi = SummaryApi(mockDio);
  });

  group('SummaryApi', () {
    // create: 요약 태스크 생성 성공 테스트
    test('create가 minutesTaskId로 요약 태스크를 생성하고 응답을 반환해야 함', () async {
      // Arrange
      when(() => mockDio.post(any(), data: any(named: 'data'))).thenAnswer(
        (_) async => Response(
          data: {'task_id': 'sum-001', 'status': 'pending'},
          statusCode: 201,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await summaryApi.create('min-001');

      // Assert
      expect(result['task_id'], 'sum-001');
      expect(result['status'], 'pending');
      verify(() =>
              mockDio.post('/summaries', data: {'minutes_task_id': 'min-001'}))
          .called(1);
    });

    // create: 네트워크 오류 시 예외 전파 테스트
    test('create가 네트워크 오류 시 DioException을 전파해야 함', () async {
      // Arrange
      when(() => mockDio.post(any(), data: any(named: 'data'))).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          message: '연결 오류',
        ),
      );

      // Act & Assert
      expect(() => summaryApi.create('min-001'), throwsA(isA<DioException>()));
    });

    // getStatus: 태스크 상태 조회 성공 테스트
    test('getStatus가 태스크 상태를 올바르게 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {'task_id': 'sum-001', 'status': 'completed', 'progress': 100},
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await summaryApi.getStatus('sum-001');

      // Assert
      expect(result['status'], 'completed');
      expect(result['progress'], 100);
      verify(() => mockDio.get('/summaries/sum-001/status')).called(1);
    });

    // getResult: 요약 결과 조회 성공 테스트 (key_decisions, next_steps 포함)
    test('getResult가 summary_text, key_decisions, next_steps를 포함한 결과를 반환해야 함',
        () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'summary_text': '회의 요약입니다.',
            'action_items': [
              {'task': '예산 검토', 'priority': 'high'},
            ],
            'key_decisions': ['예산 증액 결정'],
            'next_steps': ['예산안 작성', '팀 공유'],
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await summaryApi.getResult('sum-001');

      // Assert
      expect(result['summary_text'], '회의 요약입니다.');
      expect(result['key_decisions'], hasLength(1));
      expect(result['next_steps'], hasLength(2));
      verify(() => mockDio.get('/summaries/sum-001')).called(1);
    });

    // getResult: 오류 시 예외 전파 테스트
    test('getResult가 404 오류 시 DioException을 전파해야 함', () async {
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
      expect(() => summaryApi.getResult('unknown-id'),
          throwsA(isA<DioException>()));
    });

    test('createSmartSummary가 목적별 스마트 요약 payload를 전송해야 함', () async {
      // Arrange
      when(() => mockDio.post(any(), data: any(named: 'data'))).thenAnswer(
        (_) async => Response(
          data: {
            'task_id': 'smart-001',
            'status': 'completed',
            'result': {
              'summary_content': {'summary_text': '강의 노트 요약'},
            },
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await summaryApi.createSmartSummary(
        'min-001',
        summaryMode: 'lecture_notes',
        length: 'short',
        focusAreas: ['decisions_only'],
        includeSentiment: false,
      );

      // Assert
      expect(result['task_id'], 'smart-001');
      verify(
        () => mockDio.post(
          '/smart-summary/min-001',
          data: {
            'summary_mode': 'lecture_notes',
            'length': 'short',
            'focus_areas': ['decisions_only'],
            'include_sentiment': false,
          },
        ),
      ).called(1);
    });

    test('getSmartSummaryModes가 사용 가능한 목적별 요약 모드를 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'modes': [
              {'value': 'lecture_notes', 'label': '강의 노트'},
              {'value': 'action_only', 'label': '액션만'},
              {'value': 'soap_note', 'label': 'SOAP 노트'},
            ],
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await summaryApi.getSmartSummaryModes();

      // Assert
      expect(result, hasLength(3));
      expect(result.first['value'], 'lecture_notes');
      expect(result.last['value'], 'soap_note');
      verify(() => mockDio.get('/smart-summary/modes')).called(1);
    });

    test('getSmartSummaryHistory가 회의록별 저장된 목적별 요약을 반환해야 함', () async {
      // Arrange
      when(() => mockDio.get(any())).thenAnswer(
        (_) async => Response(
          data: {
            'minutes_task_id': 'min-001',
            'histories': {
              'lecture_notes': [
                {'summary_text': '저장된 강의 노트'},
              ],
            },
          },
          statusCode: 200,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      final result = await summaryApi.getSmartSummaryHistory('min-001');

      // Assert
      expect(result['minutes_task_id'], 'min-001');
      expect(result['histories'], isA<Map<String, dynamic>>());
      verify(() => mockDio.get('/smart-summary/history/min-001')).called(1);
    });

    // delete: 태스크 삭제 성공 테스트
    test('delete가 태스크를 삭제하고 완료해야 함', () async {
      // Arrange
      when(() => mockDio.delete(any())).thenAnswer(
        (_) async => Response(
          data: null,
          statusCode: 204,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      // Act
      await summaryApi.delete('sum-001');

      // Assert: 예외 없이 완료
      verify(() => mockDio.delete('/summaries/sum-001')).called(1);
    });
  });
}
