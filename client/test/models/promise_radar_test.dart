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
          'responsibility_scores': [
            {
              'owner': '김기수',
              'assigned_user_id': 'user-1',
              'score': 68,
              'risk_level': 'high',
              'open_count': 2,
              'completed_count': 1,
              'delayed_count': 0,
              'blocked_count': 1,
              'overdue_count': 1,
              'unconfirmed_count': 1,
              'recurring_count': 1,
              'completion_rate': 0.333,
              'reasons': ['기한 초과 1개', '차단 1개'],
            }
          ],
          'meeting_series': [
            {
              'series_key': '릴리스 주간 회의',
              'title': '릴리스 주간 회의',
              'meeting_count': 2,
              'first_seen_at': '2026-06-24T00:00:00Z',
              'last_seen_at': '2026-07-01T00:00:00Z',
              'latest_task_id': 'sum-1',
              'open_count': 2,
              'overdue_count': 1,
              'high_risk_count': 1,
              'owners': ['김기수'],
              'next_questions': ['QA 체크리스트 상태는 확인됐습니까?'],
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
      expect(result.nextMeetingBriefing!.responsibilityScores.single.score, 68);
      expect(result.nextMeetingBriefing!.meetingSeries.single.meetingCount, 2);
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
        'checkpoints': ['우선 확인: 김기수 · QA 체크리스트'],
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
      expect(preMeeting.checkpoints.single, contains('김기수'));
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
        'responsibility_scores': [
          {
            'owner': '김기수',
            'score': 72,
            'risk_level': 'high',
            'open_count': 3,
            'completed_count': 1,
            'delayed_count': 1,
            'blocked_count': 0,
            'overdue_count': 1,
            'unconfirmed_count': 1,
            'recurring_count': 2,
            'completion_rate': 0.25,
            'reasons': ['반복 약속 2개'],
          }
        ],
        'meeting_series': [
          {
            'series_key': 'release weekly',
            'title': 'Release Weekly',
            'meeting_count': 3,
            'first_seen_at': '2026-06-17T00:00:00Z',
            'last_seen_at': '2026-07-01T00:00:00Z',
            'latest_task_id': 'sum-3',
            'open_count': 3,
            'overdue_count': 1,
            'high_risk_count': 1,
            'owners': ['김기수'],
            'next_questions': ['릴리스 테스트 상태는 확인됐습니까?'],
          }
        ],
      });

      expect(dashboard.openCount, 3);
      expect(dashboard.urgentPromises.single.teamId, 'team-1');
      expect(dashboard.urgentPromises.single.notificationSentAt, isNotNull);
      expect(dashboard.recentChanges.single.eventType, 'merged');
      expect(dashboard.responsibilityScores.single.riskLevel, 'high');
      expect(dashboard.meetingSeries.single.latestTaskId, 'sum-3');

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

    test('parses digest preference and Google Tasks sync contracts', () {
      final preference = PromiseDigestPreference.fromJson({
        'scope': 'owner:user-1',
        'enabled': true,
        'cadence': 'weekly',
        'local_time': '08:30',
        'timezone': 'Asia/Seoul',
        'quiet_hours_start': '22:00',
        'quiet_hours_end': '07:00',
        'updated_at': '2026-07-01T00:00:00Z',
      });
      expect(preference.enabled, isTrue);
      expect(preference.cadence, 'weekly');

      const update = PromiseDigestPreferenceUpdateRequest(
        enabled: true,
        cadence: 'daily',
      );
      expect(update.toJson()['local_time'], '08:30');

      final tasklists = PromiseGoogleTaskListResponse.fromJson({
        'tasklists': [
          {
            'id': '@default',
            'title': 'My Tasks',
            'updated': '2026-07-01T00:00:00Z',
          }
        ],
      });
      expect(tasklists.tasklists.single.title, 'My Tasks');

      const syncRequest = PromiseExternalTaskSyncRequest(
        accessToken: 'token',
        tasklist: '@default',
        externalId: 'task-1',
      );
      expect(syncRequest.toJson()['external_id'], 'task-1');

      final syncResponse = PromiseExternalTaskSyncResponse.fromJson({
        'ledger_entry_id': 'ledger-1',
        'provider': 'google_tasks',
        'synced': true,
        'status': 'completed',
        'message': '동기화했습니다.',
        'sync_contract': {
          'idempotency_key': 'promise:google_tasks:ledger-1',
        },
      });
      expect(syncResponse.status, 'completed');
      expect(syncResponse.syncContract?['idempotency_key'],
          'promise:google_tasks:ledger-1');

      const taskUpdate = PromiseExternalTaskUpdateRequest(
        accessToken: 'token',
        tasklist: '@default',
        externalId: 'task-1',
        status: 'completed',
        title: 'QA 체크리스트',
      );
      expect(taskUpdate.toJson()['status'], 'completed');
      expect(taskUpdate.toJson()['title'], 'QA 체크리스트');

      final insight = PromiseLearningInsight.fromJson({
        'scope': 'owner:user-1',
        'autopilot_threshold': 0.78,
        'status_thresholds': {'completed': 0.82},
        'feedback_count': 5,
        'false_positive_count': 2,
        'confirmed_count': 3,
        'assignee_correction_count': 1,
        'status_attention': ['completed'],
        'recommended_policy': 'preview_only',
        'insights': ['완료 오판이 감지됐습니다.'],
        'next_actions': ['Review Inbox 확정을 우선하세요.'],
      });
      expect(insight.recommendedPolicy, 'preview_only');
      expect(insight.statusThresholds['completed'], 0.82);

      final trend = PromiseResponsibilityTrend.fromJson({
        'owner': '김기수',
        'current_score': 74,
        'risk_level': 'high',
        'direction': 'worsening',
        'points': [
          {
            'period_start': '2026-07-01',
            'score': 74,
            'open_count': 2,
            'completed_count': 0,
            'delayed_count': 1,
            'blocked_count': 0,
            'overdue_count': 1,
            'unconfirmed_count': 1,
            'recurring_count': 1,
          }
        ],
      });
      expect(trend.points.single.overdueCount, 1);

      final seriesTimeline = PromiseMeetingSeriesTimeline.fromJson({
        'series_key': 'release weekly',
        'title': 'Release Weekly',
        'meeting_count': 1,
        'first_seen_at': '2026-07-01T00:00:00Z',
        'last_seen_at': '2026-07-01T00:00:00Z',
        'items': [
          {
            'series_key': 'release weekly',
            'task_id': 'sum-1',
            'title': 'Release Weekly',
            'seen_at': '2026-07-01T00:00:00Z',
            'open_count': 1,
            'overdue_count': 0,
            'high_risk_count': 1,
            'owners': ['김기수'],
            'promises': [
              {
                'id': 'ledger-1',
                'canonical_key': 'qa',
                'canonical_text': 'QA 체크리스트',
                'text': 'QA 체크리스트',
                'status': 'open',
                'priority': 'high',
                'risk_level': 'high',
                'confidence': 0.9,
                'occurrences': 1,
                'first_seen_at': '2026-07-01T00:00:00Z',
                'last_seen_at': '2026-07-01T00:00:00Z',
                'user_confirmed': false,
              }
            ],
            'questions': ['QA 체크리스트 상태를 확인했습니까?'],
          }
        ],
      });
      expect(seriesTimeline.items.single.promises.single.text, 'QA 체크리스트');

      final reconcile = PromiseExternalTaskReconcileResponse.fromJson({
        'provider': 'google_tasks',
        'checked_count': 3,
        'linked_count': 1,
        'needs_sync_count': 1,
        'requires_oauth': true,
        'items': [
          {
            'ledger_entry': {
              'id': 'ledger-1',
              'canonical_key': 'qa',
              'canonical_text': 'QA 체크리스트',
              'text': 'QA 체크리스트',
              'status': 'completed',
              'priority': 'high',
              'risk_level': 'high',
              'confidence': 0.9,
              'occurrences': 1,
              'first_seen_at': '2026-07-01T00:00:00Z',
              'last_seen_at': '2026-07-01T00:00:00Z',
              'user_confirmed': true,
            },
            'provider': 'google_tasks',
            'tasklist': '@default',
            'external_id': 'task-1',
            'ledger_status': 'completed',
            'external_status': 'needsAction',
            'needs_sync': true,
            'direction': 'push_to_external',
            'issue': '상태가 다릅니다.',
            'sync_contract': {
              'idempotency_key': 'promise:google_tasks:ledger-1',
            },
          }
        ],
      });
      expect(reconcile.items.single.needsSync, isTrue);
      expect(reconcile.items.single.externalId, 'task-1');
    });

    test('parses command center aggregate response', () {
      final center = PromiseCommandCenter.fromJson({
        'generated_at': '2026-07-02T00:00:00Z',
        'dashboard': {
          'open_count': 4,
          'high_risk_count': 1,
          'overdue_count': 2,
          'due_soon_count': 1,
          'blocked_count': 0,
          'unconfirmed_count': 1,
          'owner_hotspots': [],
          'urgent_promises': [],
          'recent_changes': [],
          'responsibility_scores': [],
          'meeting_series': [],
        },
        'review_queue': {
          'task_id': 'all',
          'queue_count': 2,
          'actionable_count': 1,
          'conflict_count': 1,
          'items': [],
        },
        'learning_insight': {
          'scope': 'owner:user-1',
          'autopilot_threshold': 0.78,
          'status_thresholds': {'completed': 0.84},
          'status_sample_counts': {'completed': 5},
          'status_false_positive_rate': {'completed': 0.4},
          'feedback_count': 7,
          'false_positive_count': 2,
          'confirmed_count': 5,
          'assignee_correction_count': 1,
          'alias_graph_size': 3,
          'scope_breakdown': {'feedback': 7, 'owner_aliases': 3},
          'scope_recommendations': ['개인 데이터를 팀 정책으로 승격하세요.'],
          'evidence_lock_enabled': true,
          'status_attention': ['completed'],
          'recommended_policy': 'preview_only',
          'insights': ['완료 오판이 감지됐습니다.'],
          'next_actions': ['검토함 확정을 우선하세요.'],
        },
        'learning_telemetry': {
          'generated_at': '2026-07-02T00:00:00Z',
          'scope': 'owner:user-1',
          'event_count': 9,
          'feedback_event_count': 7,
          'status_segments': [
            {
              'dimension': 'status',
              'value': 'completed',
              'sample_count': 5,
              'confirmed_count': 3,
              'false_positive_count': 2,
              'correction_count': 1,
              'precision': 0.6,
              'false_positive_rate': 0.4,
              'notes': ['preview-only 권장'],
            }
          ],
          'owner_segments': [],
          'locale_segments': [],
          'payload_shape_segments': [],
          'recommendations': ['completed는 preview-only로 유지하세요.'],
        },
        'digest': {
          'cadence': 'daily',
          'title': '오늘의 약속 레이더',
          'generated_at': '2026-07-02T00:00:00Z',
          'open_count': 4,
          'overdue_count': 2,
          'due_soon_count': 1,
          'high_risk_count': 1,
          'lines': ['기한 초과 2개'],
          'promises': [],
        },
        'pre_meeting_brief': {
          'title': '회의 시작 전 약속 브리프',
          'readiness_score': 64,
          'summary': '확인할 약속이 있습니다.',
          'promises': [],
          'questions': ['기한 초과 약속을 확인했습니까?'],
          'checkpoints': ['우선 확인: 김기수'],
        },
        'live_coach': {
          'generated_at': '2026-07-02T00:00:00Z',
          'readiness_score': 64,
          'prompt_count': 1,
          'prompts': [
            {
              'key': 'checkpoint:0',
              'label': '체크포인트',
              'prompt': '우선 확인: 김기수',
              'severity': 'warning',
            }
          ],
          'notes': ['회의 중 확인 prompt를 표시합니다.'],
        },
        'external_reconcile': {
          'provider': 'google_tasks',
          'checked_count': 3,
          'linked_count': 1,
          'needs_sync_count': 1,
          'requires_oauth': true,
          'items': [],
        },
        'accuracy_report': {
          'generated_at': '2026-07-02T00:00:00Z',
          'fixture_path':
              'backend/tests/fixtures/promise_radar_accuracy_cases.json',
          'source_manifest_path':
              'backend/tests/fixtures/promise_radar_real_meeting_sources.json',
          'evaluation': {
            'case_count': 629,
            'correct_count': 629,
            'accuracy': 1.0,
            'status_precision': {'completed': 1.0},
            'failures': [],
          },
          'status_counts': {'completed': 58, 'open': 87},
          'source_counts': {'synthetic': 67},
          'coverage': {'real_meeting_target': 1.0},
          'source_quality': {},
          'quality_warnings': [],
          'real_meeting_case_count': 562,
          'target_case_count': 560,
          'below_target': false,
        },
        'extraction_recall': {
          'generated_at': '2026-07-02T00:00:00Z',
          'fixture_path':
              'backend/tests/fixtures/promise_radar_extraction_cases.json',
          'evaluation': {
            'case_count': 50,
            'expected_count': 50,
            'extracted_count': 50,
            'matched_count': 50,
            'recall': 1.0,
            'failures': [],
          },
          'real_meeting_case_count': 50,
          'target_case_count': 50,
          'below_target': false,
        },
        'evidence_audit': {
          'locked_count': 1,
          'weak_evidence_count': 1,
          'missing_timestamp_count': 1,
          'missing_speaker_count': 0,
          'marker_hit_count': 3,
          'average_similarity': 0.84,
          'notes': ['근거 확인 필요'],
        },
        'memory_graph': {
          'node_count': 6,
          'edge_count': 5,
          'recurring_series_count': 1,
          'changed_cluster_count': 1,
          'delayed_cluster_count': 2,
          'owner_alias_count': 3,
          'nodes': [
            {
              'id': 'owner:SPEAKER_01',
              'label': 'SPEAKER_01',
              'kind': 'owner',
              'weight': 81,
              'risk_level': 'high',
            }
          ],
          'edges': [
            {
              'source': 'owner:SPEAKER_01',
              'target': 'promise:1',
              'relationship': 'owns',
              'weight': 1,
            }
          ],
          'narrative': ['반복 회의 1개에서 미해결 약속 흐름을 추적합니다.'],
        },
        'shadow_mode': {
          'candidate_count': 2,
          'would_apply_count': 1,
          'preview_only_count': 1,
          'blocked_by_evidence_count': 1,
          'conflict_count': 1,
          'status_distribution': {'completed': 1, 'delayed': 1},
          'average_confidence': 0.78,
          'learning_value': '확정 결과를 threshold 학습에 반영합니다.',
          'notes': ['Evidence Lock 미충족 후보는 보류합니다.'],
        },
        'evidence_permissions': {
          'scope': 'owner:user-1',
          'export_allowed': false,
          'redaction_required': true,
          'contains_speaker_data': true,
          'contains_timestamp_data': true,
          'allowed_evidence_count': 1,
          'blocked_export_count': 2,
          'policy_notes': ['외부 공유 전 speaker/timestamp 식별자를 마스킹하세요.'],
        },
        'evidence_room': {
          'scope': 'owner:user-1',
          'share_ready_count': 1,
          'redaction_required_count': 1,
          'blocked_count': 2,
          'default_ttl_hours': 72,
          'policy_notes': ['원문 transcript는 기본 redaction됩니다.'],
        },
        'team_scorecard': {
          'risk_score': 76,
          'owner_count': 2,
          'open_count': 4,
          'overdue_count': 2,
          'high_risk_count': 1,
          'recurring_series_count': 1,
          'weakest_owner': 'SPEAKER_01',
          'strongest_owner': '김기수',
          'recommendations': ['기한 초과 약속은 다음 회의 첫 안건으로 올리세요.'],
        },
        'autopilot_quarantine': {
          'quarantined_count': 1,
          'rejected_count': 1,
          'affected_statuses': {'completed': 2},
          'affected_entries': ['ledger-1'],
          'notes': ['격리된 자동 판정은 검토함에 유지합니다.'],
        },
        'meeting_recipe': {
          'recipe_key': 'risk_review',
          'label': 'Risk Review',
          'owner_required': true,
          'due_date_required': true,
          'default_autopilot_mode': 'preview_only',
          'high_risk_keywords': ['지연', '계약'],
          'prompt_templates': ['담당자와 기한을 확인하세요.'],
          'recommended_integrations': ['Google Tasks'],
        },
        'google_tasks_oauth': {
          'provider': 'google_tasks',
          'scope': 'https://www.googleapis.com/auth/tasks',
          'auth_url_hint': 'https://accounts.google.com/o/oauth2/v2/auth',
          'redirect_uri_required': true,
          'callback_path': '/api/v1/promise-radar/google-tasks/oauth/callback',
          'production_ready': true,
          'missing_setup': [],
          'required_backend_env': ['GOOGLE_CLIENT_ID'],
          'verification_steps': ['실기기 tasklist 조회 확인'],
          'steps': ['Google Tasks scope 승인'],
          'token_handling': '요청 시에만 access token 사용',
          'security_notes': ['state/nonce 검증'],
        },
        'actions': [
          {
            'key': 'open_extraction_recall_report',
            'label': '약속 추출 누락 보고서',
            'method': 'GET',
            'route': '/api/v1/promise-radar/accuracy/extraction-report',
            'enabled': true,
            'requires_confirmation': false,
            'reason': 'Recall 100%',
            'payload': {},
          }
        ],
        'focus_items': [
          {
            'key': 'google_tasks_oauth',
            'label': 'Google Tasks OAuth 필요',
            'severity': 'warning',
            'count': 1,
            'action': 'Tasks scope 승인을 완료하세요.',
          }
        ],
      });

      expect(center.dashboard.openCount, 4);
      expect(center.reviewQueue.conflictCount, 1);
      expect(center.learningInsight.statusSampleCounts['completed'], 5);
      expect(center.learningInsight.statusFalsePositiveRate['completed'], 0.4);
      expect(center.learningInsight.aliasGraphSize, 3);
      expect(center.learningInsight.scopeBreakdown['feedback'], 7);
      expect(center.learningTelemetry.eventCount, 9);
      expect(center.learningTelemetry.statusSegments.single.falsePositiveRate,
          0.4);
      expect(center.liveCoach.promptCount, 1);
      expect(center.evidenceAudit.weakEvidenceCount, 1);
      expect(center.memoryGraph.nodeCount, 6);
      expect(center.memoryGraph.ownerAliasCount, 3);
      expect(center.shadowMode.blockedByEvidenceCount, 1);
      expect(center.evidencePermissions.exportAllowed, isFalse);
      expect(center.evidenceRoom.blockedCount, 2);
      expect(center.teamScorecard.riskScore, 76);
      expect(center.autopilotQuarantine.affectedStatuses['completed'], 2);
      expect(center.meetingRecipe.recipeKey, 'risk_review');
      expect(center.googleTasksOAuth.scope,
          'https://www.googleapis.com/auth/tasks');
      expect(center.googleTasksOAuth.productionReady, isTrue);
      expect(center.accuracyReport.evaluation.caseCount, 629);
      expect(center.accuracyReport.realMeetingCaseCount, 562);
      expect(center.extractionRecall.evaluation.recall, 1.0);
      expect(center.actions.single.key, 'open_extraction_recall_report');
      expect(center.focusItems.single.key, 'google_tasks_oauth');
    });

    test('parses accuracy report, evidence comparison, and identity confidence',
        () {
      final report = PromiseAccuracyReport.fromJson({
        'generated_at': '2026-07-01T00:00:00Z',
        'fixture_path':
            'backend/tests/fixtures/promise_radar_accuracy_cases.json',
        'source_manifest_path':
            'backend/tests/fixtures/promise_radar_real_meeting_sources.json',
        'evaluation': {
          'case_count': 172,
          'correct_count': 172,
          'accuracy': 1.0,
          'status_precision': {'completed': 1.0},
          'failures': [],
        },
        'status_counts': {'completed': 48, 'open': 81},
        'source_counts': {'4P6bVZqSKpw': 18},
        'real_meeting_case_count': 112,
        'target_case_count': 100,
        'below_target': false,
      });
      expect(report.evaluation.caseCount, 172);
      expect(report.realMeetingCaseCount, 112);
      expect(report.belowTarget, isFalse);

      final comparison = PromiseEvidenceComparison.fromJson({
        'ledger_entry_id': 'ledger-1',
        'previous_text': 'QA 체크리스트 작성 예정',
        'current_text': 'QA 체크리스트 작성 완료했습니다.',
        'previous_similarity': 0.41,
        'current_similarity': 0.88,
        'similarity_delta': 0.47,
        'shared_terms': ['체크리스트'],
        'previous_evidence': [
          {
            'source_task_id': 'sum-1',
            'meeting_link': '/results/sum-1',
            'transcript': 'QA 체크리스트 작성 예정',
          }
        ],
        'current_pack': {
          'ledger_entry_id': 'ledger-1',
          'source_task_id': 'sum-2',
          'matched_text': 'QA 체크리스트 작성 완료했습니다.',
          'similarity': 0.88,
          'marker_hits': ['완료'],
          'confidence_factors': ['근거 있음'],
          'evidence': [],
          'captured_at': '2026-07-01T00:00:00Z',
        },
        'summary': '현재 자동 판정 근거가 강합니다.',
      });
      expect(comparison.currentPack!.markerHits.single, '완료');
      expect(comparison.sharedTerms.single, '체크리스트');

      final entry = PromiseLedgerEntry.fromJson({
        'id': 'ledger-1',
        'canonical_key': 'qa',
        'canonical_text': 'QA 체크리스트',
        'text': 'QA 체크리스트',
        'status': 'open',
        'priority': 'high',
        'risk_level': 'high',
        'confidence': 0.9,
        'occurrences': 1,
        'first_seen_at': '2026-07-01T00:00:00Z',
        'last_seen_at': '2026-07-01T00:00:00Z',
        'evidence': [],
        'identity_confidence': 0.82,
        'identity_confidence_factors': ['담당자 이름', '화자 라벨'],
      });
      expect(entry.identityConfidence, 0.82);
      expect(entry.identityConfidenceFactors, contains('화자 라벨'));
    });
  });
}
