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
        'ledger_entries': [
          {
            'id': 'ledger-1',
            'canonical_key': 'qa checklist',
            'canonical_text': 'QA 체크리스트 마무리',
            'text': 'QA 체크리스트 마무리',
            'owner': '김기수',
            'speaker_label': 'SPEAKER_01',
            'status': 'open',
            'priority': 'high',
            'risk_level': 'medium',
            'confidence': 0.91,
            'due_date': '오늘',
            'occurrences': 2,
            'first_seen_at': '2026-06-23T00:00:00Z',
            'last_seen_at': '2026-06-30T00:00:00Z',
            'user_confirmed': false,
            'action_item_id': 'action-1',
            'quality': {
              'score': 82,
              'level': 'good',
              'strengths': ['담당자 또는 화자 근거가 있습니다.'],
              'issues': ['완료 기준 또는 검증 단서가 부족합니다.'],
            },
            'assignee_suggestions': [
              {
                'user_id': 'user-1',
                'display_name': '김기수',
                'email': 'kiminbean@example.com',
                'confidence': 0.92,
                'rationale': '회의에서 추출된 담당자 이름이 일치합니다.',
              }
            ],
            'evidence': [
              {
                'source_task_id': 'min-1',
                'meeting_link': '/results/min-1',
                'transcript': 'QA 체크리스트를 마무리하겠습니다.',
                'speaker': '김기수',
                'speaker_label': 'SPEAKER_01',
                'voiceprint_similarity': 0.91,
                'start_seconds': 12.3,
                'end_seconds': 18.9,
              }
            ],
          }
        ],
        'next_meeting_briefing': {
          'title': '다음 회의 전 확인할 약속',
          'high_risk_count': 1,
          'overdue_count': 0,
          'due_soon_count': 1,
          'owner_hotspots': [
            {
              'owner': '김기수',
              'open_promises': 1,
              'stale_promises': 0,
              'recurring_promises': 1,
              'risk_score': 24,
              'latest_promises': ['QA 체크리스트 마무리'],
            }
          ],
          'promises': [],
          'questions': ['QA 체크리스트 진행 상태를 확인했습니까?'],
          'reminder_candidates': [
            {
              'ledger_entry_id': 'ledger-1',
              'title': '약속 확인: QA 체크리스트 마무리',
              'owner': '김기수',
              'calendar_event': {'source': 'promise_radar'},
            }
          ],
        },
        'autopilot_assessments': [
          {
            'ledger_entry_id': 'ledger-1',
            'previous_status': 'open',
            'suggested_status': 'completed',
            'applied': true,
            'confidence': 0.84,
            'reason': '완료 신호가 확인됐습니다.',
            'explanation': {
              'ledger_entry_id': 'ledger-1',
              'matched_task_id': 'sum-1',
              'matched_text': 'QA 체크리스트 작성 완료했습니다.',
              'similarity': 0.77,
              'overlap_terms': ['체크리스트'],
              'confidence_factors': ['회의 원문 근거가 연결되어 있습니다.'],
              'rationale': '현재 회의 발화가 원장 약속과 강하게 일치합니다.',
              'evidence': [],
            },
          }
        ],
        'semantic_enrichment_status': 'zai_applied',
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
      expect(result.ledgerEntries.single.actionItemId, 'action-1');
      expect(result.ledgerEntries.single.quality!.score, 82);
      expect(result.ledgerEntries.single.assigneeSuggestions.single.displayName,
          '김기수');
      expect(result.ledgerEntries.single.evidence.single.startSeconds, 12.3);
      expect(result.nextMeetingBriefing!.dueSoonCount, 1);
      expect(
        result.nextMeetingBriefing!.reminderCandidates.single
            .calendarEvent!['source'],
        'promise_radar',
      );
      expect(result.semanticEnrichmentStatus, 'zai_applied');
      expect(result.autopilotAssessments.single.applied, isTrue);
      expect(result.followUpQuestions.single, contains('QA 체크리스트'));
    });

    test('serializes ledger update request without null fields', () {
      const request = PromiseLedgerUpdateRequest(
        status: 'completed',
        userConfirmed: true,
      );

      expect(request.toJson(), {
        'status': 'completed',
        'user_confirmed': true,
      });
    });

    test('parses learning, timeline, digest, external, and accuracy responses',
        () {
      final assessmentJson = <String, dynamic>{
        'ledger_entry_id': 'ledger-1',
        'previous_status': 'open',
        'suggested_status': 'completed',
        'applied': false,
        'requires_confirmation': true,
        'evidence_locked': true,
        'conflict_detected': false,
        'threshold': 0.8,
        'confidence': 0.84,
        'reason': '완료 신호가 확인됐습니다.',
        'explanation': {
          'ledger_entry_id': 'ledger-1',
          'similarity': 0.7,
          'overlap_terms': [],
          'confidence_factors': [],
          'rationale': '일치합니다.',
          'evidence': [],
        },
        'evidence_pack': {
          'ledger_entry_id': 'ledger-1',
          'source_task_id': 'sum-1',
          'matched_text': '완료했습니다.',
          'similarity': 0.7,
          'marker_hits': ['완료'],
          'confidence_factors': ['근거 있음'],
          'evidence': [],
          'captured_at': '2026-07-01T01:00:00Z',
        },
      };
      final autopilot = PromiseAutopilotResponse.fromJson({
        'task_id': 'sum-1',
        'autopilot_threshold': 0.72,
        'status_thresholds': {'completed': 0.8},
        'evidence_lock_enforced': true,
        'preview_mode': true,
        'assessed_count': 2,
        'applied_count': 1,
        'assessments': [assessmentJson],
      });
      expect(autopilot.autopilotThreshold, 0.72);
      expect(autopilot.statusThresholds['completed'], 0.8);
      expect(autopilot.evidenceLockEnforced, isTrue);
      expect(autopilot.previewMode, isTrue);
      expect(
          autopilot.assessments.single.evidencePack!.markerHits.single, '완료');

      final reviewQueue = PromiseAutopilotReviewQueue.fromJson({
        'task_id': 'sum-1',
        'queue_count': 1,
        'actionable_count': 1,
        'conflict_count': 0,
        'items': [
          {
            'ledger_entry': {
              'id': 'ledger-1',
              'canonical_key': 'qa',
              'canonical_text': 'QA 체크리스트',
              'text': 'QA 체크리스트',
              'status': 'open',
              'priority': 'high',
              'risk_level': 'medium',
              'confidence': 0.8,
              'occurrences': 1,
              'first_seen_at': '2026-07-01T00:00:00Z',
              'last_seen_at': '2026-07-01T00:00:00Z',
              'evidence': [],
            },
            'assessment': assessmentJson,
            'queued_at': '2026-07-01T01:00:00Z',
            'decision_required': true,
          }
        ],
      });
      expect(reviewQueue.items.single.ledgerEntry.text, 'QA 체크리스트');
      expect(reviewQueue.items.single.assessment.suggestedStatus, 'completed');

      final policy = PromiseAutomationPolicy.fromJson({
        'scope': 'team:1',
        'mode': 'completed_only',
        'allowed_auto_statuses': ['completed'],
        'high_risk_requires_review': true,
        'assignee_change_requires_review': true,
        'conflict_requires_review': true,
      });
      expect(policy.mode, 'completed_only');
      const policyRequest = PromiseAutomationPolicyUpdateRequest(
        mode: 'preview_only',
      );
      expect(policyRequest.toJson()['mode'], 'preview_only');

      final feedback = PromiseLearningFeedbackResponse.fromJson({
        'ledger_entry_id': 'ledger-1',
        'recorded': true,
        'learning_profile': {
          'scope': 'owner:user-1',
          'autopilot_threshold': 0.75,
          'status_thresholds': {'completed': 0.81},
          'false_positive_count': 2,
          'confirmed_count': 1,
          'status_false_positive_count': {'completed': 2},
          'status_confirmed_count': {'delayed': 1},
          'assignee_correction_count': 1,
          'evidence_lock_enabled': true,
          'learned_owner_aliases': {'SPEAKER_01': '김기수'},
          'owner_aliases': [
            {
              'alias': 'SPEAKER_01',
              'canonical_owner': '김기수',
              'speaker_label': 'SPEAKER_01',
              'confidence': 0.9,
              'source_count': 3,
            }
          ],
        },
      });
      expect(feedback.learningProfile.falsePositiveCount, 2);
      expect(feedback.learningProfile.learnedOwnerAliases['SPEAKER_01'], '김기수');
      expect(feedback.learningProfile.statusThresholds['completed'], 0.81);
      expect(feedback.learningProfile.ownerAliases.single.alias, 'SPEAKER_01');

      final timeline = PromiseTimelineResponse.fromJson({
        'ledger_entry_id': 'ledger-1',
        'current_status': 'completed',
        'items': [
          {
            'id': 'event-1',
            'event_type': 'autopilot_applied',
            'label': '자동 판정이 적용됐습니다.',
            'created_at': '2026-07-01T01:00:00Z',
            'status_before': 'open',
            'status_after': 'completed',
            'confidence': 0.82,
          }
        ],
      });
      expect(timeline.items.single.statusAfter, 'completed');

      final preMeeting = PromisePreMeetingBrief.fromJson({
        'title': '회의 시작 전 약속 브리프',
        'readiness_score': 76,
        'summary': '회의 전 확인할 약속 1개가 있습니다.',
        'promises': [
          {
            'id': 'ledger-1',
            'canonical_key': 'qa',
            'canonical_text': 'QA 체크리스트',
            'text': 'QA 체크리스트',
            'status': 'open',
            'priority': 'high',
            'risk_level': 'medium',
            'confidence': 0.9,
            'occurrences': 2,
            'first_seen_at': '2026-07-01T00:00:00Z',
            'last_seen_at': '2026-07-01T00:00:00Z',
            'user_confirmed': false,
          }
        ],
        'questions': ['QA 체크리스트 상태는 확인됐습니까?'],
      });
      expect(preMeeting.promises.single.text, 'QA 체크리스트');

      final digest = PromiseDigest.fromJson({
        'cadence': 'daily',
        'title': '오늘의 약속 레이더',
        'generated_at': '2026-07-01T00:00:00Z',
        'open_count': 3,
        'overdue_count': 1,
        'due_soon_count': 1,
        'high_risk_count': 1,
        'lines': ['열린 약속 3개'],
        'promises': [],
      });
      expect(digest.lines.single, '열린 약속 3개');

      final external = PromiseExternalExportResponse.fromJson({
        'ledger_entry_id': 'ledger-1',
        'provider': 'google_tasks',
        'sent': false,
        'payload': {
          'task': {'title': 'Promise Radar: QA 체크리스트'}
        },
        'message': 'Google Tasks payload가 생성됐습니다.',
      });
      expect((external.payload['task'] as Map<String, dynamic>)['title'],
          contains('Promise Radar'));

      const exportRequest =
          PromiseExternalExportRequest(provider: 'google_tasks');
      expect(exportRequest.toJson(), {
        'provider': 'google_tasks',
        'dry_run': true,
        'tasklist': '@default',
      });

      final evaluation = PromiseAccuracyEvaluation.fromJson({
        'case_count': 6,
        'correct_count': 5,
        'accuracy': 0.833,
        'status_precision': {'completed': 1.0},
        'failures': [],
      });
      expect(evaluation.statusPrecision['completed'], 1.0);
    });

    test('parses task link response', () {
      final response = PromiseTaskLinkResponse.fromJson({
        'ledger_entry_id': 'ledger-1',
        'action_item_id': 'action-1',
        'title': 'QA 체크리스트 마무리',
        'status': 'pending',
      });

      expect(response.actionItemId, 'action-1');
      expect(response.status, 'pending');
    });

    test('parses dashboard, history, merge, split, and notification responses',
        () {
      final dashboard = PromiseRadarDashboard.fromJson({
        'open_count': 3,
        'high_risk_count': 1,
        'overdue_count': 1,
        'due_soon_count': 2,
        'blocked_count': 0,
        'unconfirmed_count': 1,
        'owner_hotspots': [
          {
            'owner': '김기수',
            'open_promises': 2,
            'stale_promises': 1,
            'recurring_promises': 1,
            'risk_score': 54,
            'latest_promises': ['QA 체크리스트'],
          }
        ],
        'urgent_promises': [
          {
            'id': 'ledger-1',
            'canonical_key': 'qa',
            'canonical_text': 'QA 체크리스트',
            'text': 'QA 체크리스트',
            'team_id': 'team-1',
            'assigned_user_id': 'user-1',
            'status': 'open',
            'priority': 'high',
            'risk_level': 'high',
            'confidence': 0.9,
            'occurrences': 2,
            'first_seen_at': '2026-07-01T00:00:00Z',
            'last_seen_at': '2026-07-01T00:00:00Z',
            'user_confirmed': true,
            'notification_sent_at': '2026-07-01T01:00:00Z',
          }
        ],
        'recent_changes': [
          {
            'id': 'event-1',
            'ledger_entry_id': 'ledger-1',
            'event_type': 'merged',
            'created_at': '2026-07-01T01:00:00Z',
            'new_value': {
              'merged_entry_ids': ['ledger-2']
            },
          }
        ],
      });

      expect(dashboard.openCount, 3);
      expect(dashboard.urgentPromises.single.teamId, 'team-1');
      expect(dashboard.urgentPromises.single.notificationSentAt, isNotNull);
      expect(dashboard.recentChanges.single.eventType, 'merged');

      final merge = PromiseLedgerMergeResponse.fromJson({
        'target': {
          'id': 'ledger-1',
          'canonical_key': 'qa',
          'canonical_text': 'QA 체크리스트',
          'text': 'QA 체크리스트',
          'status': 'open',
          'priority': 'high',
          'risk_level': 'medium',
          'confidence': 0.9,
          'occurrences': 3,
          'first_seen_at': '2026-07-01T00:00:00Z',
          'last_seen_at': '2026-07-01T00:00:00Z',
          'user_confirmed': true,
        },
        'merged_entry_ids': ['ledger-2'],
      });
      expect(merge.mergedEntryIds.single, 'ledger-2');
      expect(merge.target.occurrences, 3);

      final split = PromiseLedgerSplitResponse.fromJson({
        'original': {
          'id': 'ledger-1',
          'canonical_key': 'qa',
          'canonical_text': 'QA 체크리스트',
          'text': 'QA 체크리스트',
          'status': 'open',
          'priority': 'high',
          'risk_level': 'medium',
          'confidence': 0.9,
          'occurrences': 3,
          'first_seen_at': '2026-07-01T00:00:00Z',
          'last_seen_at': '2026-07-01T00:00:00Z',
          'user_confirmed': true,
        },
        'created': {
          'id': 'ledger-3',
          'canonical_key': 'release',
          'canonical_text': '릴리스 테스트',
          'text': '릴리스 테스트',
          'status': 'open',
          'priority': 'medium',
          'risk_level': 'low',
          'confidence': 0.7,
          'occurrences': 1,
          'first_seen_at': '2026-07-01T00:00:00Z',
          'last_seen_at': '2026-07-01T00:00:00Z',
          'user_confirmed': true,
        },
      });
      expect(split.created.text, '릴리스 테스트');

      final dispatch = PromiseNotificationDispatchResponse.fromJson({
        'considered_count': 1,
        'sent_count': 1,
        'failure_count': 0,
        'invalid_tokens': [],
        'notified_entry_ids': ['ledger-1'],
      });
      expect(dispatch.notifiedEntryIds.single, 'ledger-1');

      final calendar = PromiseCalendarExportResponse.fromJson({
        'ledger_entry_id': 'ledger-1',
        'title': '약속 확인: QA 체크리스트',
        'due_at': '2026-07-01T09:00:00Z',
        'ics_filename': 'promise-ledger-1.ics',
        'ics_content': 'BEGIN:VCALENDAR',
        'google_calendar_url': 'https://calendar.google.com/calendar/render',
      });
      expect(calendar.icsContent, contains('VCALENDAR'));

      final explanation = PromiseMatchExplanation.fromJson({
        'ledger_entry_id': 'ledger-1',
        'matched_text': 'QA 체크리스트 작성 완료했습니다.',
        'similarity': 0.8,
        'overlap_terms': ['체크리스트'],
        'confidence_factors': ['근거 있음'],
        'rationale': '강하게 일치합니다.',
        'evidence': [],
      });
      expect(explanation.overlapTerms.single, '체크리스트');
    });
  });
}
