import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/study_pack.dart';
import 'package:voice_to_textnote/providers/study_pack_provider.dart';
import 'package:voice_to_textnote/services/study_pack_api.dart';

class MockStudyPackApi extends Mock implements StudyPackApi {}

void main() {
  late MockStudyPackApi api;
  late ProviderContainer container;

  StudyPack pack(String notes) => StudyPack(
        taskId: 'min-001',
        mode: 'lecture',
        language: 'ko',
        keyConcepts: const [],
        flashcards: const [],
        quizQuestions: const [],
        studyNotes: notes,
        sourceRefs: const [],
        createdAt: '2026-06-21T00:00:00+00:00',
      );

  setUp(() {
    api = MockStudyPackApi();
    container = ProviderContainer(
      overrides: [studyPackApiProvider.overrideWithValue(api)],
    );
  });

  tearDown(() => container.dispose());

  test('loads cached study pack first', () async {
    when(() => api.get(
          any(),
          mode: any(named: 'mode'),
          language: any(named: 'language'),
        )).thenAnswer((_) async => pack('cached'));

    final result = await container.read(
      studyPackProvider(const StudyPackRequest(taskId: 'min-001')).future,
    );

    expect(result.studyNotes, 'cached');
    verify(() => api.get('min-001', mode: 'lecture', language: 'ko')).called(1);
    verifyNever(() => api.create(any()));
  });

  test('creates study pack when cache is missing', () async {
    when(() => api.get(
          any(),
          mode: any(named: 'mode'),
          language: any(named: 'language'),
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
    when(() => api.create(any(),
            mode: any(named: 'mode'), language: any(named: 'language')))
        .thenAnswer((_) async => pack('created'));

    final result = await container.read(
      studyPackProvider(
              const StudyPackRequest(taskId: 'min-001', mode: 'interview'))
          .future,
    );

    expect(result.studyNotes, 'created');
    verify(() => api.create('min-001', mode: 'interview', language: 'ko'))
        .called(1);
  });

  test('regenerate forces refresh', () async {
    when(() => api.get(
          any(),
          mode: any(named: 'mode'),
          language: any(named: 'language'),
        )).thenAnswer((_) async => pack('cached'));
    when(() => api.create(
          any(),
          mode: any(named: 'mode'),
          language: any(named: 'language'),
          forceRefresh: any(named: 'forceRefresh'),
        )).thenAnswer((_) async => pack('fresh'));

    const request = StudyPackRequest(taskId: 'min-001', mode: 'sermon');
    await container.read(studyPackProvider(request).future);
    await container.read(studyPackProvider(request).notifier).regenerate();

    expect(
        container.read(studyPackProvider(request)).value!.studyNotes, 'fresh');
    verify(
      () => api.create(
        'min-001',
        mode: 'sermon',
        language: 'ko',
        forceRefresh: true,
      ),
    ).called(1);
  });
}
