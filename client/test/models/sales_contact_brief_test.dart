import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/sales_contact_brief.dart';

void main() {
  group('SalesContactBrief', () {
    test('fromJson parses contact, deal, actions, and source refs', () {
      final result = SalesContactBrief.fromJson({
        'task_id': 'min-sales-001',
        'contact': {
          'name': '김민수',
          'company': 'Acme',
          'role': 'CTO',
          'email': 'kim@example.com',
        },
        'deal': {
          'stage': 'demo_requested',
          'value_hint': 'enterprise',
          'urgency': 'high',
        },
        'customer_needs': ['보안 감사 자동화'],
        'pain_points': ['수동 감사 시간이 오래 걸림'],
        'objections': ['견적 확인 필요'],
        'next_steps': [
          {'task': '데모 일정 확정', 'owner': '영업', 'due': '다음 주 화요일'},
        ],
        'follow_up_message': '요청하신 데모 일정을 확인드리겠습니다.',
        'source_refs': [
          {'segment_index': 0, 'speaker': '고객', 'start': 12, 'text': '데모 요청'},
        ],
        'created_at': '2026-06-21T00:00:00+00:00',
      });

      expect(result.taskId, 'min-sales-001');
      expect(result.contact.name, '김민수');
      expect(result.contact.company, 'Acme');
      expect(result.deal.stage, 'demo_requested');
      expect(result.customerNeeds, ['보안 감사 자동화']);
      expect(result.nextSteps.first.task, '데모 일정 확정');
      expect(result.sourceRefs.first.speaker, '고객');
    });

    test('fromJson uses safe defaults for sparse payloads', () {
      final result = SalesContactBrief.fromJson({'task_id': 'min-sales-001'});

      expect(result.taskId, 'min-sales-001');
      expect(result.contact.name, isNull);
      expect(result.deal.stage, 'unknown');
      expect(result.customerNeeds, isEmpty);
      expect(result.nextSteps, isEmpty);
      expect(result.followUpMessage, '');
    });

    test('list response parses customer follow-up entries', () {
      final result = SalesContactListResponse.fromJson({
        'items': [
          {
            'artifact_task_id': 'sales-contact-brief:min-sales-001',
            'source_task_id': 'min-sales-001',
            'contact': {'name': '김민수', 'company': 'Acme'},
            'deal': {'stage': 'demo_requested', 'urgency': 'high'},
            'customer_needs': ['보안 감사 자동화'],
            'pain_points': ['수동 감사'],
            'next_steps': [
              {'task': '데모 일정 확정', 'owner': '영업'},
            ],
            'follow_up_message': '데모 일정을 확인드리겠습니다.',
            'crm_status': 'follow_up',
            'crm_note': '금요일 오전 재확인',
            'crm_updated_at': '2026-06-21T01:00:00+00:00',
            'created_at': '2026-06-21T00:00:00+00:00',
            'completed_at': '2026-06-21T00:00:00',
          }
        ],
        'total': 1,
        'page': 1,
        'page_size': 20,
      });

      expect(result.total, 1);
      expect(result.items.single.artifactTaskId,
          'sales-contact-brief:min-sales-001');
      expect(result.items.single.contact.company, 'Acme');
      expect(result.items.single.nextSteps.single.task, '데모 일정 확정');
      expect(result.items.single.crmStatus, 'follow_up');
      expect(result.items.single.crmNote, '금요일 오전 재확인');
      expect(result.items.single.crmUpdatedAt, '2026-06-21T01:00:00+00:00');
    });
  });
}
