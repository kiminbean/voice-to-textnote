import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/promise_radar.dart';

void main() {
  group('PromiseRadarResult', () {
    test('parses cross-meeting promise radar response', () {
      final result = PromiseRadarResult.fromJson({
        'task_id': 'sum-1',
        'generated_at': '2026-06-30T00:00:00Z',
        'headline': '확인할 약속이 있습니다.',
        'risk_score': 42,
        'analyzed_meetings': 3,
        'current_promises': [
          {
            'text': 'QA 체크리스트 마무리',
            'owner': '김기수',
            'due_date': '오늘',
            'priority': 'high',
            'source_task_id': 'sum-1',
            'source_created_at': '2026-06-30T00:00:00Z',
            'evidence': 'QA 체크리스트 마무리',
            'confidence': 0.8,
          }
        ],
        'carried_over_promises': [
          {
            'previous': {
              'text': 'QA 체크리스트 작성',
              'priority': 'high',
              'source_task_id': 'sum-0',
              'source_created_at': '2026-06-23T00:00:00Z',
              'evidence': 'QA 체크리스트 작성',
              'confidence': 0.7,
            },
            'current': {
              'text': 'QA 체크리스트 마무리',
              'priority': 'high',
              'source_task_id': 'sum-1',
              'source_created_at': '2026-06-30T00:00:00Z',
              'evidence': 'QA 체크리스트 마무리',
              'confidence': 0.8,
            },
            'similarity': 0.5,
          }
        ],
        'stale_promises': [],
        'decision_drifts': [
          {
            'previous_decision': 'IP 주소로 연결한다',
            'current_decision': '도메인으로 연결한다',
            'previous_task_id': 'sum-0',
            'current_task_id': 'sum-1',
            'similarity': 0.45,
            'evidence': '유사한 주제의 결정 변경',
          }
        ],
        'promise_chains': [
          {
            'canonical_text': 'QA 체크리스트 마무리',
            'owner': '김기수',
            'occurrences': 2,
            'first_seen_at': '2026-06-23T00:00:00Z',
            'last_seen_at': '2026-06-30T00:00:00Z',
            'age_days': 7,
            'status': 'recurring',
            'risk_level': 'medium',
            'links': [
              {
                'task_id': 'sum-0',
                'created_at': '2026-06-23T00:00:00Z',
                'text': 'QA 체크리스트 작성',
                'owner': '김기수',
              },
              {
                'task_id': 'sum-1',
                'created_at': '2026-06-30T00:00:00Z',
                'text': 'QA 체크리스트 마무리',
                'owner': '김기수',
                'due_date': '오늘',
              },
            ],
          }
        ],
        'owner_risks': [
          {
            'owner': '김기수',
            'open_promises': 2,
            'stale_promises': 1,
            'recurring_promises': 1,
            'risk_score': 46,
            'latest_promises': ['QA 체크리스트 마무리'],
          }
        ],
        'high_risk_count': 1,
        'follow_up_questions': ['QA 체크리스트 상태는 확인됐습니까?'],
      });

      expect(result.taskId, 'sum-1');
      expect(result.riskScore, 42);
      expect(result.currentPromises.single.owner, '김기수');
      expect(result.carriedOverPromises.single.similarity, 0.5);
      expect(result.decisionDrifts.single.currentDecision, '도메인으로 연결한다');
      expect(result.promiseChains.single.occurrences, 2);
      expect(result.promiseChains.single.links.last.dueDate, '오늘');
      expect(result.ownerRisks.single.owner, '김기수');
      expect(result.highRiskCount, 1);
      expect(result.followUpQuestions.single, contains('QA 체크리스트'));
    });
  });
}
