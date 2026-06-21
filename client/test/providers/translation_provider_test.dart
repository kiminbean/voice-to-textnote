import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/translation.dart';
import 'package:voice_to_textnote/providers/translation_provider.dart';
import 'package:voice_to_textnote/services/translation_api.dart';

class MockTranslationApi extends Mock implements TranslationApi {}

void main() {
  late MockTranslationApi api;
  late ProviderContainer container;

  TranslationResult result(String text) => TranslationResult(
        taskId: 'sum-001',
        sourceType: 'summary',
        sourceLanguage: 'ko',
        targetLanguage: 'en',
        translatedText: text,
        sourceExcerpt: '회의 요약',
        cached: false,
        createdAt: '2026-06-21T00:00:00+00:00',
      );

  setUp(() {
    api = MockTranslationApi();
    container = ProviderContainer(
      overrides: [translationApiProvider.overrideWithValue(api)],
    );
  });

  tearDown(() => container.dispose());

  test('loads cached translation first', () async {
    when(() => api.get(
          any(),
          targetLanguage: any(named: 'targetLanguage'),
          sourceType: any(named: 'sourceType'),
        )).thenAnswer((_) async => result('cached'));

    final value = await container.read(
      translationProvider(const TranslationRequest(
        taskId: 'sum-001',
        targetLanguage: 'en',
      )).future,
    );

    expect(value.translatedText, 'cached');
    verify(
      () => api.get(
        'sum-001',
        targetLanguage: 'en',
        sourceType: 'auto',
      ),
    ).called(1);
    verifyNever(
        () => api.create(any(), targetLanguage: any(named: 'targetLanguage')));
  });

  test('creates translation when cache is missing', () async {
    when(() => api.get(
          any(),
          targetLanguage: any(named: 'targetLanguage'),
          sourceType: any(named: 'sourceType'),
        )).thenThrow(
      DioException(
        requestOptions: RequestOptions(path: ''),
        response: Response(
          statusCode: 404,
          requestOptions: RequestOptions(path: ''),
        ),
        type: DioExceptionType.badResponse,
      ),
    );
    when(() => api.create(
          any(),
          targetLanguage: any(named: 'targetLanguage'),
          sourceLanguage: any(named: 'sourceLanguage'),
          sourceType: any(named: 'sourceType'),
        )).thenAnswer((_) async => result('created'));

    final value = await container.read(
      translationProvider(const TranslationRequest(
        taskId: 'sum-001',
        targetLanguage: 'ja',
        sourceLanguage: 'ko',
        sourceType: 'summary',
      )).future,
    );

    expect(value.translatedText, 'created');
    verify(
      () => api.create(
        'sum-001',
        targetLanguage: 'ja',
        sourceLanguage: 'ko',
        sourceType: 'summary',
      ),
    ).called(1);
  });

  test('regenerate forces refresh', () async {
    when(() => api.get(
          any(),
          targetLanguage: any(named: 'targetLanguage'),
          sourceType: any(named: 'sourceType'),
        )).thenAnswer((_) async => result('cached'));
    when(() => api.create(
          any(),
          targetLanguage: any(named: 'targetLanguage'),
          sourceLanguage: any(named: 'sourceLanguage'),
          sourceType: any(named: 'sourceType'),
          forceRefresh: any(named: 'forceRefresh'),
        )).thenAnswer((_) async => result('fresh'));

    const request = TranslationRequest(
      taskId: 'sum-001',
      targetLanguage: 'en',
      sourceType: 'summary',
    );
    await container.read(translationProvider(request).future);
    await container.read(translationProvider(request).notifier).regenerate();

    expect(
      container.read(translationProvider(request)).value!.translatedText,
      'fresh',
    );
    verify(
      () => api.create(
        'sum-001',
        targetLanguage: 'en',
        sourceType: 'summary',
        forceRefresh: true,
      ),
    ).called(1);
  });
}
