import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/sales_contact_brief_api.dart';

class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late SalesContactBriefApi api;

  setUp(() {
    mockDio = MockDio();
    api = SalesContactBriefApi(mockDio);
  });

  Map<String, dynamic> payload() => {
        'task_id': 'min-sales-001',
        'contact': {'name': '김민수', 'company': 'Acme'},
        'deal': {'stage': 'demo_requested', 'urgency': 'high'},
        'customer_needs': ['보안 감사 자동화'],
        'pain_points': ['수동 감사 시간'],
        'objections': ['견적 확인 필요'],
        'next_steps': [
          {'task': '데모 일정 확정'},
        ],
        'follow_up_message': '데모 일정을 확인드리겠습니다.',
        'source_refs': <dynamic>[],
        'created_at': '2026-06-21T00:00:00+00:00',
      };

  test('create posts language and force_refresh then parses response',
      () async {
    when(() => mockDio.post(any(), data: any(named: 'data'))).thenAnswer(
      (_) async => Response(
        data: payload(),
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );

    final result = await api.create(
      'min-sales-001',
      language: 'ko',
      forceRefresh: true,
    );

    expect(result.contact.company, 'Acme');
    verify(
      () => mockDio.post(
        '/minutes/min-sales-001/sales-contact-brief',
        data: {
          'language': 'ko',
          'force_refresh': true,
        },
      ),
    ).called(1);
  });

  test('get loads cached sales contact brief', () async {
    when(() => mockDio.get(any())).thenAnswer(
      (_) async => Response(
        data: payload(),
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );

    final result = await api.get('min-sales-001');

    expect(result.followUpMessage, '데모 일정을 확인드리겠습니다.');
    verify(
      () => mockDio.get('/minutes/min-sales-001/sales-contact-brief'),
    ).called(1);
  });
}
