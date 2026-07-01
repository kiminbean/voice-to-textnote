class PromiseRadarPromise {
  final String text;
  final String? owner;
  final String? dueDate;
  final String priority;
  final String sourceTaskId;
  final String sourceCreatedAt;
  final String evidence;
  final double confidence;

  const PromiseRadarPromise({
    required this.text,
    this.owner,
    this.dueDate,
    required this.priority,
    required this.sourceTaskId,
    required this.sourceCreatedAt,
    required this.evidence,
    required this.confidence,
  });

  factory PromiseRadarPromise.fromJson(Map<String, dynamic> json) {
    return PromiseRadarPromise(
      text: json['text'] as String? ?? '',
      owner: json['owner'] as String?,
      dueDate: json['due_date'] as String?,
      priority: json['priority'] as String? ?? 'medium',
      sourceTaskId: json['source_task_id'] as String? ?? '',
      sourceCreatedAt: json['source_created_at'] as String? ?? '',
      evidence: json['evidence'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
    );
  }
}

class PromiseRadarCarryOver {
  final PromiseRadarPromise previous;
  final PromiseRadarPromise current;
  final double similarity;

  const PromiseRadarCarryOver({
    required this.previous,
    required this.current,
    required this.similarity,
  });

  factory PromiseRadarCarryOver.fromJson(Map<String, dynamic> json) {
    return PromiseRadarCarryOver(
      previous: PromiseRadarPromise.fromJson(
        json['previous'] as Map<String, dynamic>? ?? const {},
      ),
      current: PromiseRadarPromise.fromJson(
        json['current'] as Map<String, dynamic>? ?? const {},
      ),
      similarity: (json['similarity'] as num?)?.toDouble() ?? 0,
    );
  }
}

class PromiseRadarDecisionDrift {
  final String previousDecision;
  final String currentDecision;
  final String previousTaskId;
  final String currentTaskId;
  final double similarity;
  final String evidence;

  const PromiseRadarDecisionDrift({
    required this.previousDecision,
    required this.currentDecision,
    required this.previousTaskId,
    required this.currentTaskId,
    required this.similarity,
    required this.evidence,
  });

  factory PromiseRadarDecisionDrift.fromJson(Map<String, dynamic> json) {
    return PromiseRadarDecisionDrift(
      previousDecision: json['previous_decision'] as String? ?? '',
      currentDecision: json['current_decision'] as String? ?? '',
      previousTaskId: json['previous_task_id'] as String? ?? '',
      currentTaskId: json['current_task_id'] as String? ?? '',
      similarity: (json['similarity'] as num?)?.toDouble() ?? 0,
      evidence: json['evidence'] as String? ?? '',
    );
  }
}

class PromiseRadarChainLink {
  final String taskId;
  final String createdAt;
  final String text;
  final String? owner;
  final String? dueDate;

  const PromiseRadarChainLink({
    required this.taskId,
    required this.createdAt,
    required this.text,
    this.owner,
    this.dueDate,
  });

  factory PromiseRadarChainLink.fromJson(Map<String, dynamic> json) {
    return PromiseRadarChainLink(
      taskId: json['task_id'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
      text: json['text'] as String? ?? '',
      owner: json['owner'] as String?,
      dueDate: json['due_date'] as String?,
    );
  }
}

class PromiseRadarPromiseChain {
  final String canonicalText;
  final String? owner;
  final int occurrences;
  final String firstSeenAt;
  final String lastSeenAt;
  final int ageDays;
  final String status;
  final String riskLevel;
  final List<PromiseRadarChainLink> links;

  const PromiseRadarPromiseChain({
    required this.canonicalText,
    this.owner,
    required this.occurrences,
    required this.firstSeenAt,
    required this.lastSeenAt,
    required this.ageDays,
    required this.status,
    required this.riskLevel,
    required this.links,
  });

  factory PromiseRadarPromiseChain.fromJson(Map<String, dynamic> json) {
    return PromiseRadarPromiseChain(
      canonicalText: json['canonical_text'] as String? ?? '',
      owner: json['owner'] as String?,
      occurrences: json['occurrences'] as int? ?? 0,
      firstSeenAt: json['first_seen_at'] as String? ?? '',
      lastSeenAt: json['last_seen_at'] as String? ?? '',
      ageDays: json['age_days'] as int? ?? 0,
      status: json['status'] as String? ?? 'active',
      riskLevel: json['risk_level'] as String? ?? 'low',
      links: (json['links'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarChainLink.fromJson)
          .toList(),
    );
  }
}

class PromiseRadarOwnerRisk {
  final String owner;
  final int openPromises;
  final int stalePromises;
  final int recurringPromises;
  final int riskScore;
  final List<String> latestPromises;

  const PromiseRadarOwnerRisk({
    required this.owner,
    required this.openPromises,
    required this.stalePromises,
    required this.recurringPromises,
    required this.riskScore,
    required this.latestPromises,
  });

  factory PromiseRadarOwnerRisk.fromJson(Map<String, dynamic> json) {
    return PromiseRadarOwnerRisk(
      owner: json['owner'] as String? ?? '미지정',
      openPromises: json['open_promises'] as int? ?? 0,
      stalePromises: json['stale_promises'] as int? ?? 0,
      recurringPromises: json['recurring_promises'] as int? ?? 0,
      riskScore: json['risk_score'] as int? ?? 0,
      latestPromises: (json['latest_promises'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseRadarEvidence {
  final String sourceTaskId;
  final String meetingLink;
  final String transcript;
  final String? speaker;
  final String? speakerLabel;
  final String? speakerProfileId;
  final double? voiceprintSimilarity;
  final double? startSeconds;
  final double? endSeconds;

  const PromiseRadarEvidence({
    required this.sourceTaskId,
    required this.meetingLink,
    required this.transcript,
    this.speaker,
    this.speakerLabel,
    this.speakerProfileId,
    this.voiceprintSimilarity,
    this.startSeconds,
    this.endSeconds,
  });

  factory PromiseRadarEvidence.fromJson(Map<String, dynamic> json) {
    return PromiseRadarEvidence(
      sourceTaskId: json['source_task_id'] as String? ?? '',
      meetingLink: json['meeting_link'] as String? ?? '',
      transcript: json['transcript'] as String? ?? '',
      speaker: json['speaker'] as String?,
      speakerLabel: json['speaker_label'] as String?,
      speakerProfileId: json['speaker_profile_id'] as String?,
      voiceprintSimilarity: (json['voiceprint_similarity'] as num?)?.toDouble(),
      startSeconds: (json['start_seconds'] as num?)?.toDouble(),
      endSeconds: (json['end_seconds'] as num?)?.toDouble(),
    );
  }
}

class PromiseLedgerEntry {
  final String id;
  final String canonicalKey;
  final String canonicalText;
  final String text;
  final String? owner;
  final String? teamId;
  final String? assignedUserId;
  final String? speakerLabel;
  final String? speakerProfileId;
  final String status;
  final String priority;
  final String riskLevel;
  final double confidence;
  final String? dueDate;
  final String? dueAt;
  final String? reminderAt;
  final String? notificationSentAt;
  final int occurrences;
  final String firstSeenAt;
  final String lastSeenAt;
  final List<PromiseRadarEvidence> evidence;
  final bool userConfirmed;
  final String? semanticSummary;
  final Map<String, dynamic>? calendarEvent;
  final String? actionItemId;
  final String? dismissedReason;

  const PromiseLedgerEntry({
    required this.id,
    required this.canonicalKey,
    required this.canonicalText,
    required this.text,
    this.owner,
    this.teamId,
    this.assignedUserId,
    this.speakerLabel,
    this.speakerProfileId,
    required this.status,
    required this.priority,
    required this.riskLevel,
    required this.confidence,
    this.dueDate,
    this.dueAt,
    this.reminderAt,
    this.notificationSentAt,
    required this.occurrences,
    required this.firstSeenAt,
    required this.lastSeenAt,
    required this.evidence,
    required this.userConfirmed,
    this.semanticSummary,
    this.calendarEvent,
    this.actionItemId,
    this.dismissedReason,
  });

  factory PromiseLedgerEntry.fromJson(Map<String, dynamic> json) {
    return PromiseLedgerEntry(
      id: json['id'] as String? ?? '',
      canonicalKey: json['canonical_key'] as String? ?? '',
      canonicalText: json['canonical_text'] as String? ?? '',
      text: json['text'] as String? ?? '',
      owner: json['owner'] as String?,
      teamId: json['team_id'] as String?,
      assignedUserId: json['assigned_user_id'] as String?,
      speakerLabel: json['speaker_label'] as String?,
      speakerProfileId: json['speaker_profile_id'] as String?,
      status: json['status'] as String? ?? 'open',
      priority: json['priority'] as String? ?? 'medium',
      riskLevel: json['risk_level'] as String? ?? 'low',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      dueDate: json['due_date'] as String?,
      dueAt: json['due_at'] as String?,
      reminderAt: json['reminder_at'] as String?,
      notificationSentAt: json['notification_sent_at'] as String?,
      occurrences: json['occurrences'] as int? ?? 1,
      firstSeenAt: json['first_seen_at'] as String? ?? '',
      lastSeenAt: json['last_seen_at'] as String? ?? '',
      evidence: (json['evidence'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarEvidence.fromJson)
          .toList(),
      userConfirmed: json['user_confirmed'] as bool? ?? false,
      semanticSummary: json['semantic_summary'] as String?,
      calendarEvent: json['calendar_event'] as Map<String, dynamic>?,
      actionItemId: json['action_item_id'] as String?,
      dismissedReason: json['dismissed_reason'] as String?,
    );
  }
}

class PromiseLedgerHistoryEntry {
  final String id;
  final String ledgerEntryId;
  final String eventType;
  final String? actorUserId;
  final Map<String, dynamic>? oldValue;
  final Map<String, dynamic>? newValue;
  final String? note;
  final String createdAt;

  const PromiseLedgerHistoryEntry({
    required this.id,
    required this.ledgerEntryId,
    required this.eventType,
    this.actorUserId,
    this.oldValue,
    this.newValue,
    this.note,
    required this.createdAt,
  });

  factory PromiseLedgerHistoryEntry.fromJson(Map<String, dynamic> json) {
    return PromiseLedgerHistoryEntry(
      id: json['id'] as String? ?? '',
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      eventType: json['event_type'] as String? ?? '',
      actorUserId: json['actor_user_id'] as String?,
      oldValue: json['old_value'] as Map<String, dynamic>?,
      newValue: json['new_value'] as Map<String, dynamic>?,
      note: json['note'] as String?,
      createdAt: json['created_at'] as String? ?? '',
    );
  }
}

class PromiseLedgerMergeResponse {
  final PromiseLedgerEntry target;
  final List<String> mergedEntryIds;

  const PromiseLedgerMergeResponse({
    required this.target,
    required this.mergedEntryIds,
  });

  factory PromiseLedgerMergeResponse.fromJson(Map<String, dynamic> json) {
    return PromiseLedgerMergeResponse(
      target: PromiseLedgerEntry.fromJson(
        json['target'] as Map<String, dynamic>? ?? const <String, dynamic>{},
      ),
      mergedEntryIds: (json['merged_entry_ids'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseLedgerSplitResponse {
  final PromiseLedgerEntry original;
  final PromiseLedgerEntry created;

  const PromiseLedgerSplitResponse({
    required this.original,
    required this.created,
  });

  factory PromiseLedgerSplitResponse.fromJson(Map<String, dynamic> json) {
    return PromiseLedgerSplitResponse(
      original: PromiseLedgerEntry.fromJson(
        json['original'] as Map<String, dynamic>? ?? const <String, dynamic>{},
      ),
      created: PromiseLedgerEntry.fromJson(
        json['created'] as Map<String, dynamic>? ?? const <String, dynamic>{},
      ),
    );
  }
}

class PromiseReminderCandidate {
  final String ledgerEntryId;
  final String title;
  final String? owner;
  final String? dueAt;
  final String? reminderAt;
  final Map<String, dynamic>? calendarEvent;

  const PromiseReminderCandidate({
    required this.ledgerEntryId,
    required this.title,
    this.owner,
    this.dueAt,
    this.reminderAt,
    this.calendarEvent,
  });

  factory PromiseReminderCandidate.fromJson(Map<String, dynamic> json) {
    return PromiseReminderCandidate(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      owner: json['owner'] as String?,
      dueAt: json['due_at'] as String?,
      reminderAt: json['reminder_at'] as String?,
      calendarEvent: json['calendar_event'] as Map<String, dynamic>?,
    );
  }
}

class PromiseTaskLinkResponse {
  final String ledgerEntryId;
  final String actionItemId;
  final String title;
  final String status;

  const PromiseTaskLinkResponse({
    required this.ledgerEntryId,
    required this.actionItemId,
    required this.title,
    required this.status,
  });

  factory PromiseTaskLinkResponse.fromJson(Map<String, dynamic> json) {
    return PromiseTaskLinkResponse(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      actionItemId: json['action_item_id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      status: json['status'] as String? ?? '',
    );
  }
}

class PromiseNotificationDispatchResponse {
  final int consideredCount;
  final int sentCount;
  final int failureCount;
  final List<String> invalidTokens;
  final List<String> notifiedEntryIds;

  const PromiseNotificationDispatchResponse({
    required this.consideredCount,
    required this.sentCount,
    required this.failureCount,
    required this.invalidTokens,
    required this.notifiedEntryIds,
  });

  factory PromiseNotificationDispatchResponse.fromJson(
    Map<String, dynamic> json,
  ) {
    return PromiseNotificationDispatchResponse(
      consideredCount: json['considered_count'] as int? ?? 0,
      sentCount: json['sent_count'] as int? ?? 0,
      failureCount: json['failure_count'] as int? ?? 0,
      invalidTokens: (json['invalid_tokens'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      notifiedEntryIds: (json['notified_entry_ids'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseNextMeetingBriefing {
  final String title;
  final int highRiskCount;
  final int overdueCount;
  final int dueSoonCount;
  final List<PromiseRadarOwnerRisk> ownerHotspots;
  final List<PromiseLedgerEntry> promises;
  final List<String> questions;
  final List<PromiseReminderCandidate> reminderCandidates;

  const PromiseNextMeetingBriefing({
    required this.title,
    required this.highRiskCount,
    required this.overdueCount,
    required this.dueSoonCount,
    required this.ownerHotspots,
    required this.promises,
    required this.questions,
    required this.reminderCandidates,
  });

  factory PromiseNextMeetingBriefing.fromJson(Map<String, dynamic> json) {
    return PromiseNextMeetingBriefing(
      title: json['title'] as String? ?? '다음 회의 전 확인할 약속',
      highRiskCount: json['high_risk_count'] as int? ?? 0,
      overdueCount: json['overdue_count'] as int? ?? 0,
      dueSoonCount: json['due_soon_count'] as int? ?? 0,
      ownerHotspots: (json['owner_hotspots'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarOwnerRisk.fromJson)
          .toList(),
      promises: (json['promises'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseLedgerEntry.fromJson)
          .toList(),
      questions: (json['questions'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      reminderCandidates: (json['reminder_candidates'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseReminderCandidate.fromJson)
          .toList(),
    );
  }
}

class PromiseRadarDashboard {
  final int openCount;
  final int highRiskCount;
  final int overdueCount;
  final int dueSoonCount;
  final int blockedCount;
  final int unconfirmedCount;
  final List<PromiseRadarOwnerRisk> ownerHotspots;
  final List<PromiseLedgerEntry> urgentPromises;
  final List<PromiseLedgerHistoryEntry> recentChanges;

  const PromiseRadarDashboard({
    required this.openCount,
    required this.highRiskCount,
    required this.overdueCount,
    required this.dueSoonCount,
    required this.blockedCount,
    required this.unconfirmedCount,
    required this.ownerHotspots,
    required this.urgentPromises,
    required this.recentChanges,
  });

  factory PromiseRadarDashboard.fromJson(Map<String, dynamic> json) {
    return PromiseRadarDashboard(
      openCount: json['open_count'] as int? ?? 0,
      highRiskCount: json['high_risk_count'] as int? ?? 0,
      overdueCount: json['overdue_count'] as int? ?? 0,
      dueSoonCount: json['due_soon_count'] as int? ?? 0,
      blockedCount: json['blocked_count'] as int? ?? 0,
      unconfirmedCount: json['unconfirmed_count'] as int? ?? 0,
      ownerHotspots: (json['owner_hotspots'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarOwnerRisk.fromJson)
          .toList(),
      urgentPromises: (json['urgent_promises'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseLedgerEntry.fromJson)
          .toList(),
      recentChanges: (json['recent_changes'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseLedgerHistoryEntry.fromJson)
          .toList(),
    );
  }
}

class PromiseLedgerUpdateRequest {
  final String? status;
  final String? text;
  final String? owner;
  final String? teamId;
  final String? assignedUserId;
  final String? priority;
  final String? dueDate;
  final DateTime? dueAt;
  final DateTime? reminderAt;
  final bool? userConfirmed;
  final String? dismissedReason;

  const PromiseLedgerUpdateRequest({
    this.status,
    this.text,
    this.owner,
    this.teamId,
    this.assignedUserId,
    this.priority,
    this.dueDate,
    this.dueAt,
    this.reminderAt,
    this.userConfirmed,
    this.dismissedReason,
  });

  Map<String, dynamic> toJson() {
    return {
      if (status != null) 'status': status,
      if (text != null) 'text': text,
      if (owner != null) 'owner': owner,
      if (teamId != null) 'team_id': teamId,
      if (assignedUserId != null) 'assigned_user_id': assignedUserId,
      if (priority != null) 'priority': priority,
      if (dueDate != null) 'due_date': dueDate,
      if (dueAt != null) 'due_at': dueAt!.toIso8601String(),
      if (reminderAt != null) 'reminder_at': reminderAt!.toIso8601String(),
      if (userConfirmed != null) 'user_confirmed': userConfirmed,
      if (dismissedReason != null) 'dismissed_reason': dismissedReason,
    };
  }
}

class PromiseRadarResult {
  final String taskId;
  final String generatedAt;
  final String headline;
  final int riskScore;
  final int analyzedMeetings;
  final List<PromiseRadarPromise> currentPromises;
  final List<PromiseRadarCarryOver> carriedOverPromises;
  final List<PromiseRadarPromise> stalePromises;
  final List<PromiseRadarDecisionDrift> decisionDrifts;
  final List<PromiseRadarPromiseChain> promiseChains;
  final List<PromiseRadarOwnerRisk> ownerRisks;
  final int highRiskCount;
  final List<PromiseLedgerEntry> ledgerEntries;
  final PromiseNextMeetingBriefing? nextMeetingBriefing;
  final String semanticEnrichmentStatus;
  final List<String> followUpQuestions;

  const PromiseRadarResult({
    required this.taskId,
    required this.generatedAt,
    required this.headline,
    required this.riskScore,
    required this.analyzedMeetings,
    required this.currentPromises,
    required this.carriedOverPromises,
    required this.stalePromises,
    required this.decisionDrifts,
    required this.promiseChains,
    required this.ownerRisks,
    required this.highRiskCount,
    this.ledgerEntries = const [],
    this.nextMeetingBriefing,
    this.semanticEnrichmentStatus = 'deterministic',
    required this.followUpQuestions,
  });

  factory PromiseRadarResult.fromJson(Map<String, dynamic> json) {
    return PromiseRadarResult(
      taskId: json['task_id'] as String? ?? '',
      generatedAt: json['generated_at'] as String? ?? '',
      headline: json['headline'] as String? ?? '',
      riskScore: json['risk_score'] as int? ?? 0,
      analyzedMeetings: json['analyzed_meetings'] as int? ?? 0,
      currentPromises: (json['current_promises'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarPromise.fromJson)
          .toList(),
      carriedOverPromises:
          (json['carried_over_promises'] as List<dynamic>? ?? [])
              .whereType<Map<String, dynamic>>()
              .map(PromiseRadarCarryOver.fromJson)
              .toList(),
      stalePromises: (json['stale_promises'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarPromise.fromJson)
          .toList(),
      decisionDrifts: (json['decision_drifts'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarDecisionDrift.fromJson)
          .toList(),
      promiseChains: (json['promise_chains'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarPromiseChain.fromJson)
          .toList(),
      ownerRisks: (json['owner_risks'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarOwnerRisk.fromJson)
          .toList(),
      highRiskCount: json['high_risk_count'] as int? ?? 0,
      ledgerEntries: (json['ledger_entries'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseLedgerEntry.fromJson)
          .toList(),
      nextMeetingBriefing: json['next_meeting_briefing'] is Map<String, dynamic>
          ? PromiseNextMeetingBriefing.fromJson(
              json['next_meeting_briefing'] as Map<String, dynamic>,
            )
          : null,
      semanticEnrichmentStatus:
          json['semantic_enrichment_status'] as String? ?? 'deterministic',
      followUpQuestions: (json['follow_up_questions'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}
