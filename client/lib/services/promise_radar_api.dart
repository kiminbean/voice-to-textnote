import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/promise_radar.dart';

import 'api_client.dart';

final promiseRadarApiProvider = Provider<PromiseRadarApi>((ref) {
  final dio = ref.watch(dioProvider);
  return PromiseRadarApi(dio);
});

class PromiseRadarApi {
  final Dio _dio;

  PromiseRadarApi(this._dio);

  Future<PromiseRadarResult> getRadar(
    String taskId, {
    int limit = 30,
    String? teamId,
  }) async {
    final response = await _dio.get(
      '/promise-radar/$taskId',
      queryParameters: {
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseRadarResult.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<PromiseLedgerEntry>> listLedger({
    List<String>? statuses,
    String? teamId,
    int limit = 50,
  }) async {
    final response = await _dio.get(
      '/promise-radar/ledger',
      queryParameters: {
        if (statuses != null && statuses.isNotEmpty) 'status': statuses,
        if (teamId != null) 'team_id': teamId,
        'limit': limit,
      },
    );
    return (response.data as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(PromiseLedgerEntry.fromJson)
        .toList();
  }

  Future<PromiseNextMeetingBriefing> getNextMeetingBriefing({
    String? teamId,
    int limit = 30,
  }) async {
    final response = await _dio.get(
      '/promise-radar/briefing/next',
      queryParameters: {
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseNextMeetingBriefing.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromisePreMeetingBrief> getPreMeetingBrief({
    String? teamId,
    int limit = 8,
  }) async {
    final response = await _dio.get(
      '/promise-radar/briefing/pre-meeting',
      queryParameters: {
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromisePreMeetingBrief.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseDigest> getDigest({
    String cadence = 'daily',
    String? teamId,
    int limit = 12,
  }) async {
    final response = await _dio.get(
      '/promise-radar/digest',
      queryParameters: {
        'cadence': cadence,
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseDigest.fromJson(response.data as Map<String, dynamic>);
  }

  Future<PromiseLearningProfile> getLearningProfile({
    String? teamId,
  }) async {
    final response = await _dio.get(
      '/promise-radar/learning-profile',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseLearningProfile.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseRadarDashboard> getDashboard({
    String? teamId,
    int limit = 50,
  }) async {
    final response = await _dio.get(
      '/promise-radar/dashboard',
      queryParameters: {
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseRadarDashboard.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseLedgerEntry> updateLedgerEntry(
    String entryId,
    PromiseLedgerUpdateRequest request, {
    String? teamId,
  }) async {
    final response = await _dio.patch(
      '/promise-radar/ledger/$entryId',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
      data: request.toJson(),
    );
    return PromiseLedgerEntry.fromJson(response.data as Map<String, dynamic>);
  }

  Future<PromiseAutopilotResponse> runAutopilot(
    String taskId, {
    bool apply = true,
    String? teamId,
    int limit = 50,
  }) async {
    final response = await _dio.post(
      '/promise-radar/autopilot/$taskId',
      queryParameters: {
        'apply': apply,
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseAutopilotResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseAutopilotResponse> previewAutopilot(
    String taskId, {
    String? teamId,
    int limit = 50,
  }) async {
    final response = await _dio.post(
      '/promise-radar/autopilot/$taskId/preview',
      queryParameters: {
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseAutopilotResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseAutopilotAssessment> confirmAutopilotAssessment(
    String entryId, {
    required String taskId,
    String? suggestedStatus,
    String? note,
    String? teamId,
  }) async {
    final response = await _dio.post(
      '/promise-radar/ledger/$entryId/autopilot-confirm',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
      data: {
        'task_id': taskId,
        if (suggestedStatus != null) 'suggested_status': suggestedStatus,
        if (note != null) 'note': note,
      },
    );
    return PromiseAutopilotAssessment.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseMatchExplanation> explainLedgerEntry(
    String entryId, {
    String? taskId,
    String? teamId,
  }) async {
    final response = await _dio.get(
      '/promise-radar/ledger/$entryId/explain',
      queryParameters: {
        if (taskId != null) 'task_id': taskId,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseMatchExplanation.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseReminderCandidate> createCalendarCandidate(
    String entryId, {
    String? teamId,
  }) async {
    final response = await _dio.post(
      '/promise-radar/ledger/$entryId/calendar',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseReminderCandidate.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseCalendarExportResponse> exportCalendarEvent(
    String entryId, {
    String? teamId,
  }) async {
    final response = await _dio.post(
      '/promise-radar/ledger/$entryId/calendar/export',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseCalendarExportResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<List<PromiseAssigneeSuggestion>> suggestAssignees(
    String entryId, {
    String? teamId,
    int limit = 5,
  }) async {
    final response = await _dio.get(
      '/promise-radar/ledger/$entryId/assignee-suggestions',
      queryParameters: {
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return (response.data as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(PromiseAssigneeSuggestion.fromJson)
        .toList();
  }

  Future<PromiseLearningFeedbackResponse> recordLearningFeedback(
    String entryId,
    PromiseLearningFeedbackRequest request, {
    String? teamId,
  }) async {
    final response = await _dio.post(
      '/promise-radar/ledger/$entryId/learning-feedback',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
      data: request.toJson(),
    );
    return PromiseLearningFeedbackResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseTimelineResponse> getTimeline(
    String entryId, {
    String? teamId,
    int limit = 50,
  }) async {
    final response = await _dio.get(
      '/promise-radar/ledger/$entryId/timeline',
      queryParameters: {
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseTimelineResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseExternalExportResponse> exportExternalTask(
    String entryId,
    PromiseExternalExportRequest request, {
    String? teamId,
  }) async {
    final response = await _dio.post(
      '/promise-radar/ledger/$entryId/external-task',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
      data: request.toJson(),
    );
    return PromiseExternalExportResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseTaskLinkResponse> createActionItem(
    String entryId, {
    String? teamId,
  }) async {
    final response = await _dio.post(
      '/promise-radar/ledger/$entryId/action-item',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseTaskLinkResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseLedgerMergeResponse> mergeLedgerEntries(
    String targetEntryId, {
    required List<String> sourceEntryIds,
    String? note,
    String? teamId,
  }) async {
    final response = await _dio.post(
      '/promise-radar/ledger/$targetEntryId/merge',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
      data: {
        'source_entry_ids': sourceEntryIds,
        if (note != null) 'note': note,
      },
    );
    return PromiseLedgerMergeResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseLedgerSplitResponse> splitLedgerEntry(
    String entryId, {
    required String text,
    String? owner,
    String? dueDate,
    DateTime? dueAt,
    String? priority,
    List<int> evidenceIndices = const [],
    String? note,
    String? teamId,
  }) async {
    final response = await _dio.post(
      '/promise-radar/ledger/$entryId/split',
      queryParameters: {
        if (teamId != null) 'team_id': teamId,
      },
      data: {
        'text': text,
        if (owner != null) 'owner': owner,
        if (dueDate != null) 'due_date': dueDate,
        if (dueAt != null) 'due_at': dueAt.toIso8601String(),
        if (priority != null) 'priority': priority,
        'evidence_indices': evidenceIndices,
        if (note != null) 'note': note,
      },
    );
    return PromiseLedgerSplitResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<List<PromiseLedgerHistoryEntry>> listLedgerHistory(
    String entryId, {
    String? teamId,
    int limit = 30,
  }) async {
    final response = await _dio.get(
      '/promise-radar/ledger/$entryId/history',
      queryParameters: {
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return (response.data as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(PromiseLedgerHistoryEntry.fromJson)
        .toList();
  }

  Future<PromiseNotificationDispatchResponse> dispatchDueNotifications({
    String? teamId,
    int limit = 25,
  }) async {
    final response = await _dio.post(
      '/promise-radar/ledger/notifications/due',
      queryParameters: {
        'limit': limit,
        if (teamId != null) 'team_id': teamId,
      },
    );
    return PromiseNotificationDispatchResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseAccuracyEvaluation> evaluateAccuracy(
    List<PromiseAccuracyCase> cases,
  ) async {
    final response = await _dio.post(
      '/promise-radar/accuracy/evaluate',
      data: cases.map((caseItem) => caseItem.toJson()).toList(),
    );
    return PromiseAccuracyEvaluation.fromJson(
      response.data as Map<String, dynamic>,
    );
  }
}
