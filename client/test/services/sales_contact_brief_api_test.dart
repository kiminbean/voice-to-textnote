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
    when(() => mockDio.post(
          any(),
          data: any(named: 'data'),
          options: any(named: 'options'),
        )).thenAnswer(
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
    final options = verify(
      () => mockDio.post(
        '/minutes/min-sales-001/sales-contact-brief',
        options: captureAny(named: 'options'),
        data: {
          'language': 'ko',
          'force_refresh': true,
        },
      ),
    ).captured.single as Options;
    expect(options.receiveTimeout, const Duration(minutes: 2));
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

  test('listContacts passes pagination and query parameters', () async {
    when(() =>
            mockDio.get(any(), queryParameters: any(named: 'queryParameters')))
        .thenAnswer(
      (_) async => Response(
        data: {
          'items': [
            {
              'artifact_task_id': 'sales-contact-brief:min-sales-001',
              'source_task_id': 'min-sales-001',
              'contact': {'company': 'Acme'},
              'deal': {'stage': 'demo_requested'},
              'customer_needs': ['보안 감사 자동화'],
              'pain_points': <dynamic>[],
              'next_steps': [
                {'task': '데모 일정 확정'},
              ],
              'follow_up_message': '확인드리겠습니다.',
              'crm_status': 'open',
              'crm_note': '',
              'created_at': '2026-06-21T00:00:00+00:00',
            }
          ],
          'total': 1,
          'page': 2,
          'page_size': 10,
        },
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );

    final result =
        await api.listContacts(query: ' Acme ', page: 2, pageSize: 10);

    expect(result.items.single.contact.company, 'Acme');
    verify(
      () => mockDio.get(
        '/sales-contacts',
        queryParameters: {
          'page': 2,
          'page_size': 10,
          'q': 'Acme',
        },
      ),
    ).called(1);
  });

  test('updateContactCrm patches CRM fields', () async {
    when(() => mockDio.patch(any(), data: any(named: 'data'))).thenAnswer(
      (_) async => Response(
        data: {
          'artifact_task_id': 'sales-contact-brief:min-sales-001',
          'source_task_id': 'min-sales-001',
          'contact': {'company': 'Acme'},
          'deal': {'stage': 'demo_requested'},
          'customer_needs': <dynamic>[],
          'pain_points': <dynamic>[],
          'next_steps': <dynamic>[],
          'follow_up_message': '',
          'crm_status': 'follow_up',
          'crm_note': '금요일 오전 재확인',
          'created_at': '2026-06-21T00:00:00+00:00',
        },
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );

    final result = await api.updateContactCrm(
      artifactTaskId: 'sales-contact-brief:min-sales-001',
      status: 'follow_up',
      note: '금요일 오전 재확인',
    );

    expect(result.crmStatus, 'follow_up');
    expect(result.crmNote, '금요일 오전 재확인');
    verify(
      () => mockDio.patch(
        '/sales-contacts/sales-contact-brief%3Amin-sales-001/crm',
        data: {
          'status': 'follow_up',
          'note': '금요일 오전 재확인',
        },
      ),
    ).called(1);
  });

  test('exportContactsCsv downloads CRM CSV with query', () async {
    when(
      () => mockDio.get<String>(
        any(),
        queryParameters: any(named: 'queryParameters'),
      ),
    ).thenAnswer(
      (_) async => Response<String>(
        data: 'name,company\n김민수,Acme\n',
        requestOptions: RequestOptions(path: '/sales-contacts/export.csv'),
      ),
    );

    final result = await api.exportContactsCsv(query: ' Acme ');

    expect(result, contains('김민수,Acme'));
    verify(
      () => mockDio.get<String>(
        '/sales-contacts/export.csv',
        queryParameters: {'q': 'Acme'},
      ),
    ).called(1);
  });
}
