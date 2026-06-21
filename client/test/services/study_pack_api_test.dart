import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/study_pack_api.dart';

class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late StudyPackApi api;

  setUp(() {
    mockDio = MockDio();
    api = StudyPackApi(mockDio);
  });

  Map<String, dynamic> payload() => {
        'task_id': 'min-001',
        'mode': 'lecture',
        'language': 'ko',
        'key_concepts': [
          {'term': '광합성', 'explanation': '빛 에너지 전환'},
        ],
        'flashcards': [
          {'front': '광합성?', 'back': '빛 에너지 전환'},
        ],
        'quiz_questions': [
          {'question': '광합성?', 'answer': '빛 에너지 전환'},
        ],
        'study_notes': '노트',
        'source_refs': <dynamic>[],
        'created_at': '2026-06-21T00:00:00+00:00',
      };

  test('create posts mode and force_refresh then parses response', () async {
    when(() => mockDio.post(any(), data: any(named: 'data'))).thenAnswer(
      (_) async => Response(
        data: payload(),
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );

    final result = await api.create(
      'min-001',
      mode: 'lecture',
      forceRefresh: true,
    );

    expect(result.taskId, 'min-001');
    verify(
      () => mockDio.post(
        '/minutes/min-001/study-pack',
        data: {
          'mode': 'lecture',
          'language': 'ko',
          'force_refresh': true,
        },
      ),
    ).called(1);
  });

  test('get loads cached study pack', () async {
    when(() =>
            mockDio.get(any(), queryParameters: any(named: 'queryParameters')))
        .thenAnswer(
      (_) async => Response(
        data: payload(),
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );

    final result = await api.get('min-001', mode: 'interview');

    expect(result.studyNotes, '노트');
    verify(
      () => mockDio.get(
        '/minutes/min-001/study-pack',
        queryParameters: {'mode': 'interview'},
      ),
    ).called(1);
  });
}
