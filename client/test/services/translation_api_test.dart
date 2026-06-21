import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/translation_api.dart';

class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late TranslationApi api;

  setUp(() {
    mockDio = MockDio();
    api = TranslationApi(mockDio);
  });

  Map<String, dynamic> payload() => {
        'task_id': 'sum-001',
        'source_type': 'summary',
        'source_language': 'ko',
        'target_language': 'en',
        'translated_text': 'Meeting summary',
        'source_excerpt': '회의 요약',
        'cached': false,
        'created_at': '2026-06-21T00:00:00+00:00',
      };

  test('create posts translation request and parses response', () async {
    when(() => mockDio.post(any(), data: any(named: 'data'))).thenAnswer(
      (_) async => Response(
        data: payload(),
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );

    final result = await api.create(
      'sum-001',
      targetLanguage: 'en',
      sourceLanguage: 'ko',
      sourceType: 'summary',
      forceRefresh: true,
    );

    expect(result.translatedText, 'Meeting summary');
    verify(
      () => mockDio.post(
        '/minutes/sum-001/translation',
        data: {
          'target_language': 'en',
          'source_language': 'ko',
          'source_type': 'summary',
          'force_refresh': true,
        },
      ),
    ).called(1);
  });

  test('get loads cached translation', () async {
    when(() =>
            mockDio.get(any(), queryParameters: any(named: 'queryParameters')))
        .thenAnswer(
      (_) async => Response(
        data: payload(),
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );

    final result = await api.get(
      'sum-001',
      targetLanguage: 'ja',
      sourceType: 'minutes',
    );

    expect(result.taskId, 'sum-001');
    verify(
      () => mockDio.get(
        '/minutes/sum-001/translation',
        queryParameters: {
          'target_language': 'ja',
          'source_type': 'minutes',
        },
      ),
    ).called(1);
  });
}
