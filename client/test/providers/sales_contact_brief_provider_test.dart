import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/sales_contact_brief.dart';
import 'package:voice_to_textnote/providers/sales_contact_brief_provider.dart';
import 'package:voice_to_textnote/services/sales_contact_brief_api.dart';

class MockSalesContactBriefApi extends Mock implements SalesContactBriefApi {}

void main() {
  late MockSalesContactBriefApi api;
  late ProviderContainer container;

  SalesContactBrief brief(String message) => SalesContactBrief(
        taskId: 'min-sales-001',
        contact: const SalesContactIdentity(name: '김민수', company: 'Acme'),
        deal: const SalesContactDeal(stage: 'demo_requested', urgency: 'high'),
        customerNeeds: const ['보안 감사 자동화'],
        painPoints: const [],
        objections: const [],
        nextSteps: const [SalesNextStep(task: '데모 일정 확정')],
        followUpMessage: message,
        sourceRefs: const [],
        createdAt: '2026-06-21T00:00:00+00:00',
      );

  SalesContactListResponse contactList() => const SalesContactListResponse(
        items: [
          SalesContactListItem(
            artifactTaskId: 'sales-contact-brief:min-sales-001',
            sourceTaskId: 'min-sales-001',
            contact: SalesContactIdentity(name: '김민수', company: 'Acme'),
            deal: SalesContactDeal(stage: 'demo_requested', urgency: 'high'),
            customerNeeds: ['보안 감사 자동화'],
            painPoints: [],
            nextSteps: [SalesNextStep(task: '데모 일정 확정')],
            followUpMessage: '확인드리겠습니다.',
            createdAt: '2026-06-21T00:00:00+00:00',
          ),
        ],
        total: 1,
        page: 1,
        pageSize: 20,
      );

  setUp(() {
    api = MockSalesContactBriefApi();
    container = ProviderContainer(
      overrides: [salesContactBriefApiProvider.overrideWithValue(api)],
    );
  });

  tearDown(() => container.dispose());

  test('loads cached sales brief first', () async {
    when(() => api.get(any())).thenAnswer((_) async => brief('cached'));

    final result = await container.read(
      salesContactBriefProvider(
        const SalesContactBriefRequest(taskId: 'min-sales-001'),
      ).future,
    );

    expect(result.followUpMessage, 'cached');
    verify(() => api.get('min-sales-001')).called(1);
    verifyNever(() => api.create(any()));
  });

  test('creates sales brief when cache is missing', () async {
    when(() => api.get(any())).thenThrow(
      DioException(
        requestOptions: RequestOptions(path: ''),
        response: Response(
          statusCode: 404,
          requestOptions: RequestOptions(path: ''),
        ),
        type: DioExceptionType.badResponse,
      ),
    );
    when(() => api.create(any(), language: any(named: 'language')))
        .thenAnswer((_) async => brief('created'));

    final result = await container.read(
      salesContactBriefProvider(
        const SalesContactBriefRequest(taskId: 'min-sales-001'),
      ).future,
    );

    expect(result.followUpMessage, 'created');
    verify(() => api.create('min-sales-001', language: 'ko')).called(1);
  });

  test('keeps generated sales brief warm after tab listener closes', () async {
    when(() => api.get(any())).thenAnswer((_) async => brief('warm'));

    const request = SalesContactBriefRequest(taskId: 'min-sales-001');
    final provider = salesContactBriefProvider(request);
    final subscription = container.listen(provider, (_, __) {});

    final first = await container.read(provider.future);
    subscription.close();
    await Future<void>.delayed(Duration.zero);
    final second = await container.read(provider.future);

    expect(first.followUpMessage, 'warm');
    expect(second.followUpMessage, 'warm');
    verify(() => api.get('min-sales-001')).called(1);
  });

  test('regenerate forces refresh', () async {
    when(() => api.get(any())).thenAnswer((_) async => brief('cached'));
    when(() => api.create(
          any(),
          language: any(named: 'language'),
          forceRefresh: any(named: 'forceRefresh'),
        )).thenAnswer((_) async => brief('fresh'));

    const request = SalesContactBriefRequest(taskId: 'min-sales-001');
    await container.read(salesContactBriefProvider(request).future);
    await container
        .read(salesContactBriefProvider(request).notifier)
        .regenerate();

    expect(
      container.read(salesContactBriefProvider(request)).value!.followUpMessage,
      'fresh',
    );
    verify(
      () => api.create(
        'min-sales-001',
        language: 'ko',
        forceRefresh: true,
      ),
    ).called(1);
  });

  test('loads sales contact list with query', () async {
    when(() => api.listContacts(
          query: any(named: 'query'),
          page: any(named: 'page'),
          pageSize: any(named: 'pageSize'),
        )).thenAnswer((_) async => contactList());

    const request = SalesContactListRequest(query: 'Acme');
    final result =
        await container.read(salesContactListProvider(request).future);

    expect(result.items.single.contact.company, 'Acme');
    verify(
      () => api.listContacts(query: 'Acme', page: 1, pageSize: 20),
    ).called(1);
  });
}
