import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/qa_api.dart';

class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late QAApi api;

  setUp(() {
    mockDio = MockDio();
    api = QAApi(mockDio);
  });

  test('askAcross posts question and limit then parses grounded sources',
      () async {
    when(() => mockDio.post(any(), data: any(named: 'data'))).thenAnswer(
      (_) async => Response(
        data: {
          'answer': '관련 회의 근거 1건을 찾았습니다.',
          'query': 'API 결정',
          'total': 1,
          'sources': [
            {
              'task_id': 'sum-search-001',
              'task_type': 'summary',
              'snippet': '회의 결과 <b>FastAPI</b> 사용을 결정했습니다.',
              'created_at': '2024-01-03T09:00:00',
              'completed_at': null,
            },
          ],
        },
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );

    final result = await api.askAcross(
      question: 'API 개발에서 결정된 내용은?',
      limit: 3,
    );

    expect(result.query, 'API 결정');
    expect(result.total, 1);
    expect(result.sources.single.taskId, 'sum-search-001');
    expect(result.sources.single.taskType, 'summary');
    verify(
      () => mockDio.post(
        '/qa/ask-across',
        data: {
          'question': 'API 개발에서 결정된 내용은?',
          'limit': 3,
        },
      ),
    ).called(1);
  });
}
