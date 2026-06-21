import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/sales_contact_brief.dart';
import 'package:voice_to_textnote/providers/sales_contact_brief_provider.dart';
import 'package:voice_to_textnote/screens/sales_contacts_screen.dart';

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
            createdAt: '2026-06-21T00:00:00+00:00',
          ),
        ],
        total: 1,
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
    expect(find.text('보안 감사 자동화'), findsOneWidget);
    expect(find.text('데모 일정 확정'), findsOneWidget);
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
