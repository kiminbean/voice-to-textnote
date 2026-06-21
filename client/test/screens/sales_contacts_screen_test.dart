import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/sales_contact_brief.dart';
import 'package:voice_to_textnote/providers/sales_contact_brief_provider.dart';
import 'package:voice_to_textnote/screens/sales_contacts_screen.dart';
import 'package:voice_to_textnote/services/sales_contact_brief_api.dart';

class MockSalesContactBriefApi extends Mock implements SalesContactBriefApi {}

void main() {
  SalesContactListResponse responseWithItems() =>
      const SalesContactListResponse(
        items: [
          SalesContactListItem(
            artifactTaskId: 'sales-contact-brief:min-sales-001',
            sourceTaskId: 'min-sales-001',
            contact: SalesContactIdentity(name: '김민수', company: 'Acme'),
            deal: SalesContactDeal(stage: 'demo_requested', urgency: 'high'),
            customerNeeds: ['보안 감사 자동화'],
            painPoints: ['수동 감사'],
            nextSteps: [SalesNextStep(task: '데모 일정 확정')],
            followUpMessage: '데모 일정을 확인드리겠습니다.',
            crmStatus: 'follow_up',
            crmNote: '금요일 오전 재확인',
            createdAt: '2026-06-21T00:00:00+00:00',
          ),
          SalesContactListItem(
            artifactTaskId: 'sales-contact-brief:min-sales-002',
            sourceTaskId: 'min-sales-002',
            contact: SalesContactIdentity(name: '이지은', company: 'Beta'),
            deal: SalesContactDeal(stage: 'closed', urgency: 'low'),
            customerNeeds: ['계약 갱신'],
            painPoints: ['승인 지연'],
            nextSteps: [SalesNextStep(task: '종료 사유 정리')],
            followUpMessage: '논의 내용을 기록해두겠습니다.',
            crmStatus: 'lost',
            crmNote: '다음 분기 재시도',
            createdAt: '2026-06-21T01:00:00+00:00',
          ),
        ],
        total: 2,
        page: 1,
        pageSize: 20,
      );

  testWidgets('renders sales contact cards', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          salesContactListProvider.overrideWith(
            (ref, request) async => responseWithItems(),
          ),
        ],
        child: const MaterialApp(home: SalesContactsScreen()),
      ),
    );

    await tester.pump();
    await tester.pump();

    expect(find.text('영업 고객'), findsOneWidget);
    expect(find.text('Acme · 김민수'), findsOneWidget);
    expect(find.text('후속 예정'), findsOneWidget);
    expect(find.text('금요일 오전 재확인'), findsOneWidget);
    expect(find.text('보안 감사 자동화'), findsOneWidget);
    expect(find.text('데모 일정 확정'), findsOneWidget);
  });

  testWidgets('filters contacts by lifecycle stage', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          salesContactListProvider.overrideWith(
            (ref, request) async => responseWithItems(),
          ),
        ],
        child: const MaterialApp(home: SalesContactsScreen()),
      ),
    );

    await tester.pump();
    await tester.pump();

    expect(find.text('Acme · 김민수'), findsOneWidget);
    expect(find.text('Beta · 이지은'), findsOneWidget);

    await tester.tap(find.text('종료'));
    await tester.pump();

    expect(find.text('Acme · 김민수'), findsNothing);
    expect(find.text('Beta · 이지은'), findsOneWidget);
    expect(find.text('종료 사유 정리'), findsOneWidget);
  });

  testWidgets('edits CRM memo for a sales contact', (tester) async {
    final api = MockSalesContactBriefApi();
    when(() => api.updateContactCrm(
          artifactTaskId: 'sales-contact-brief:min-sales-001',
          status: 'follow_up',
          note: '다음 주 월요일 재연락',
        )).thenAnswer((_) async => responseWithItems().items.first);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          salesContactBriefApiProvider.overrideWithValue(api),
          salesContactListProvider.overrideWith(
            (ref, request) async => responseWithItems(),
          ),
        ],
        child: const MaterialApp(home: SalesContactsScreen()),
      ),
    );

    await tester.pump();
    await tester.pump();

    await tester.tap(find.byTooltip('CRM 메모 편집').first);
    await tester.pumpAndSettle();
    await tester.enterText(
        find.widgetWithText(TextFormField, '상태'), 'follow_up');
    await tester.enterText(
        find.widgetWithText(TextFormField, '메모'), '다음 주 월요일 재연락');
    await tester.tap(find.widgetWithText(FilledButton, '저장'));
    await tester.pumpAndSettle();

    verify(() => api.updateContactCrm(
          artifactTaskId: 'sales-contact-brief:min-sales-001',
          status: 'follow_up',
          note: '다음 주 월요일 재연락',
        )).called(1);
    expect(find.text('CRM 메모를 저장했습니다'), findsOneWidget);
  });

  testWidgets('shares CRM CSV export for current search', (tester) async {
    final api = MockSalesContactBriefApi();
    final sharedPayloads = <String>[];
    when(() => api.exportContactsCsv(query: any(named: 'query')))
        .thenAnswer((_) async => 'name,company\n김민수,Acme\n');

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          salesContactBriefApiProvider.overrideWithValue(api),
          salesContactCsvShareProvider.overrideWithValue(
            (csv) async => sharedPayloads.add(csv),
          ),
          salesContactListProvider.overrideWith(
            (ref, request) async => responseWithItems(),
          ),
        ],
        child: const MaterialApp(home: SalesContactsScreen()),
      ),
    );

    await tester.pump();
    await tester.pump();
    await tester.enterText(find.byType(TextField), 'Acme');
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.byTooltip('CRM CSV 공유'));
    await tester.pumpAndSettle();

    verify(() => api.exportContactsCsv(query: 'Acme')).called(1);
    expect(sharedPayloads.single, contains('김민수,Acme'));
  });

  testWidgets('renders empty state when no sales contacts exist',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          salesContactListProvider.overrideWith(
            (ref, request) async => const SalesContactListResponse(
              items: [],
              total: 0,
              page: 1,
              pageSize: 20,
            ),
          ),
        ],
        child: const MaterialApp(home: SalesContactsScreen()),
      ),
    );

    await tester.pump();
    await tester.pump();

    expect(find.text('아직 영업 브리프가 없습니다'), findsOneWidget);
  });
}
