import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/providers/qa_provider.dart';
import 'package:voice_to_textnote/services/qa_api.dart';

class MockQAApi extends Mock implements QAApi {}

void main() {
  late MockQAApi api;
  late ProviderContainer container;

  setUp(() {
    api = MockQAApi();
    container = ProviderContainer(
      overrides: [qaApiProvider.overrideWithValue(api)],
    );
  });

  tearDown(() => container.dispose());

  test('crossMeetingAskProvider skips server call for short questions',
      () async {
    final result = await container.read(crossMeetingAskProvider(' ').future);

    expect(result.sources, isEmpty);
    expect(result.total, 0);
    verifyNever(() => api.askAcross(question: any(named: 'question')));
  });

  test('crossMeetingAskProvider calls askAcross with trimmed question',
      () async {
    when(() => api.askAcross(
          question: any(named: 'question'),
          limit: any(named: 'limit'),
        )).thenAnswer(
      (_) async => const CrossMeetingAskResponse(
        answer: '관련 회의 근거 1건을 찾았습니다.',
        sources: [
          CrossMeetingSource(
            taskId: 'sum-search-001',
            taskType: 'summary',
            snippet: 'FastAPI 결정',
            createdAt: '2024-01-03T09:00:00',
          ),
        ],
        query: 'API 결정',
        total: 1,
      ),
    );

    final result =
        await container.read(crossMeetingAskProvider('  API 결정은?  ').future);

    expect(result.sources.single.taskId, 'sum-search-001');
    verify(() => api.askAcross(question: 'API 결정은?')).called(1);
  });
}
