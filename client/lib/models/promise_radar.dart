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

class PromiseQualityScore {
  final int score;
  final String level;
  final List<String> strengths;
  final List<String> issues;

  const PromiseQualityScore({
    required this.score,
    required this.level,
    required this.strengths,
    required this.issues,
  });

  factory PromiseQualityScore.fromJson(Map<String, dynamic> json) {
    return PromiseQualityScore(
      score: json['score'] as int? ?? 0,
      level: json['level'] as String? ?? 'risky',
      strengths: (json['strengths'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      issues:
          (json['issues'] as List<dynamic>? ?? []).whereType<String>().toList(),
    );
  }
}

class PromiseAssigneeSuggestion {
  final String? userId;
  final String displayName;
  final String? email;
  final double confidence;
  final String rationale;

  const PromiseAssigneeSuggestion({
    this.userId,
    required this.displayName,
    this.email,
    required this.confidence,
    required this.rationale,
  });

  factory PromiseAssigneeSuggestion.fromJson(Map<String, dynamic> json) {
    return PromiseAssigneeSuggestion(
      userId: json['user_id'] as String?,
      displayName: json['display_name'] as String? ?? '',
      email: json['email'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      rationale: json['rationale'] as String? ?? '',
    );
  }
}

class PromiseOwnerAlias {
  final String alias;
  final String canonicalOwner;
  final String? speakerLabel;
  final String? speakerProfileId;
  final String? assignedUserId;
  final double confidence;
  final int sourceCount;

  const PromiseOwnerAlias({
    required this.alias,
    required this.canonicalOwner,
    this.speakerLabel,
    this.speakerProfileId,
    this.assignedUserId,
    required this.confidence,
    required this.sourceCount,
  });

  factory PromiseOwnerAlias.fromJson(Map<String, dynamic> json) {
    return PromiseOwnerAlias(
      alias: json['alias'] as String? ?? '',
      canonicalOwner: json['canonical_owner'] as String? ?? '',
      speakerLabel: json['speaker_label'] as String?,
      speakerProfileId: json['speaker_profile_id'] as String?,
      assignedUserId: json['assigned_user_id'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      sourceCount: json['source_count'] as int? ?? 1,
    );
  }
}

class PromiseMatchExplanation {
  final String ledgerEntryId;
  final String? matchedTaskId;
  final String? matchedText;
  final double similarity;
  final List<String> overlapTerms;
  final List<String> confidenceFactors;
  final String rationale;
  final List<PromiseRadarEvidence> evidence;

  const PromiseMatchExplanation({
    required this.ledgerEntryId,
    this.matchedTaskId,
    this.matchedText,
    required this.similarity,
    required this.overlapTerms,
    required this.confidenceFactors,
    required this.rationale,
    required this.evidence,
  });

  factory PromiseMatchExplanation.fromJson(Map<String, dynamic> json) {
    return PromiseMatchExplanation(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      matchedTaskId: json['matched_task_id'] as String?,
      matchedText: json['matched_text'] as String?,
      similarity: (json['similarity'] as num?)?.toDouble() ?? 0,
      overlapTerms: (json['overlap_terms'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      confidenceFactors: (json['confidence_factors'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      rationale: json['rationale'] as String? ?? '',
      evidence: (json['evidence'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarEvidence.fromJson)
          .toList(),
    );
  }
}

class PromiseEvidencePack {
  final String ledgerEntryId;
  final String? sourceTaskId;
  final String? matchedText;
  final double similarity;
  final List<String> markerHits;
  final List<String> confidenceFactors;
  final List<PromiseRadarEvidence> evidence;
  final String capturedAt;

  const PromiseEvidencePack({
    required this.ledgerEntryId,
    this.sourceTaskId,
    this.matchedText,
    required this.similarity,
    required this.markerHits,
    required this.confidenceFactors,
    required this.evidence,
    required this.capturedAt,
  });

  factory PromiseEvidencePack.fromJson(Map<String, dynamic> json) {
    return PromiseEvidencePack(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      sourceTaskId: json['source_task_id'] as String?,
      matchedText: json['matched_text'] as String?,
      similarity: (json['similarity'] as num?)?.toDouble() ?? 0,
      markerHits: (json['marker_hits'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      confidenceFactors: (json['confidence_factors'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      evidence: (json['evidence'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarEvidence.fromJson)
          .toList(),
      capturedAt: json['captured_at'] as String? ?? '',
    );
  }
}

class PromiseAutopilotAssessment {
  final String ledgerEntryId;
  final String previousStatus;
  final String suggestedStatus;
  final bool applied;
  final bool requiresConfirmation;
  final bool evidenceLocked;
  final bool conflictDetected;
  final String? conflictReason;
  final double threshold;
  final double confidence;
  final String reason;
  final PromiseMatchExplanation explanation;
  final PromiseEvidencePack? evidencePack;

  const PromiseAutopilotAssessment({
    required this.ledgerEntryId,
    required this.previousStatus,
    required this.suggestedStatus,
    required this.applied,
    this.requiresConfirmation = true,
    this.evidenceLocked = false,
    this.conflictDetected = false,
    this.conflictReason,
    this.threshold = 0.68,
    required this.confidence,
    required this.reason,
    required this.explanation,
    this.evidencePack,
  });

  factory PromiseAutopilotAssessment.fromJson(Map<String, dynamic> json) {
    return PromiseAutopilotAssessment(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      previousStatus: json['previous_status'] as String? ?? '',
      suggestedStatus: json['suggested_status'] as String? ?? '',
      applied: json['applied'] as bool? ?? false,
      requiresConfirmation: json['requires_confirmation'] as bool? ?? true,
      evidenceLocked: json['evidence_locked'] as bool? ?? false,
      conflictDetected: json['conflict_detected'] as bool? ?? false,
      conflictReason: json['conflict_reason'] as String?,
      threshold: (json['threshold'] as num?)?.toDouble() ?? 0.68,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      reason: json['reason'] as String? ?? '',
      explanation: PromiseMatchExplanation.fromJson(
        json['explanation'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      evidencePack: json['evidence_pack'] is Map<String, dynamic>
          ? PromiseEvidencePack.fromJson(
              json['evidence_pack'] as Map<String, dynamic>,
            )
          : null,
    );
  }
}

class PromiseAutopilotResponse {
  final String taskId;
  final double autopilotThreshold;
  final Map<String, double> statusThresholds;
  final bool evidenceLockEnforced;
  final bool previewMode;
  final int assessedCount;
  final int appliedCount;
  final List<PromiseAutopilotAssessment> assessments;

  const PromiseAutopilotResponse({
    required this.taskId,
    this.autopilotThreshold = 0.68,
    this.statusThresholds = const {},
    this.evidenceLockEnforced = true,
    this.previewMode = false,
    required this.assessedCount,
    required this.appliedCount,
    required this.assessments,
  });

  factory PromiseAutopilotResponse.fromJson(Map<String, dynamic> json) {
    return PromiseAutopilotResponse(
      taskId: json['task_id'] as String? ?? '',
      autopilotThreshold:
          (json['autopilot_threshold'] as num?)?.toDouble() ?? 0.68,
      statusThresholds:
          (json['status_thresholds'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toDouble() ?? 0.68),
      ),
      evidenceLockEnforced: json['evidence_lock_enforced'] as bool? ?? true,
      previewMode: json['preview_mode'] as bool? ?? false,
      assessedCount: json['assessed_count'] as int? ?? 0,
      appliedCount: json['applied_count'] as int? ?? 0,
      assessments: (json['assessments'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseAutopilotAssessment.fromJson)
          .toList(),
    );
  }
}

class PromiseAutopilotReviewItem {
  final PromiseLedgerEntry ledgerEntry;
  final PromiseAutopilotAssessment assessment;
  final String queuedAt;
  final bool decisionRequired;

  const PromiseAutopilotReviewItem({
    required this.ledgerEntry,
    required this.assessment,
    required this.queuedAt,
    this.decisionRequired = true,
  });

  factory PromiseAutopilotReviewItem.fromJson(Map<String, dynamic> json) {
    return PromiseAutopilotReviewItem(
      ledgerEntry: PromiseLedgerEntry.fromJson(
        json['ledger_entry'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      assessment: PromiseAutopilotAssessment.fromJson(
        json['assessment'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      queuedAt: json['queued_at'] as String? ?? '',
      decisionRequired: json['decision_required'] as bool? ?? true,
    );
  }
}

class PromiseAutopilotReviewQueue {
  final String taskId;
  final int queueCount;
  final int actionableCount;
  final int conflictCount;
  final List<PromiseAutopilotReviewItem> items;

  const PromiseAutopilotReviewQueue({
    required this.taskId,
    required this.queueCount,
    required this.actionableCount,
    required this.conflictCount,
    required this.items,
  });

  factory PromiseAutopilotReviewQueue.fromJson(Map<String, dynamic> json) {
    return PromiseAutopilotReviewQueue(
      taskId: json['task_id'] as String? ?? '',
      queueCount: json['queue_count'] as int? ?? 0,
      actionableCount: json['actionable_count'] as int? ?? 0,
      conflictCount: json['conflict_count'] as int? ?? 0,
      items: (json['items'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseAutopilotReviewItem.fromJson)
          .toList(),
    );
  }
}

class PromiseConflictResolveRequest {
  final String status;
  final String? note;

  const PromiseConflictResolveRequest({
    required this.status,
    this.note,
  });

  Map<String, dynamic> toJson() {
    return {
      'status': status,
      if (note != null) 'note': note,
    };
  }
}

class PromiseAutomationPolicy {
  final String scope;
  final String mode;
  final List<String> allowedAutoStatuses;
  final bool highRiskRequiresReview;
  final bool assigneeChangeRequiresReview;
  final bool conflictRequiresReview;
  final String? updatedAt;

  const PromiseAutomationPolicy({
    required this.scope,
    this.mode = 'safe_auto',
    this.allowedAutoStatuses = const [],
    this.highRiskRequiresReview = true,
    this.assigneeChangeRequiresReview = true,
    this.conflictRequiresReview = true,
    this.updatedAt,
  });

  factory PromiseAutomationPolicy.fromJson(Map<String, dynamic> json) {
    return PromiseAutomationPolicy(
      scope: json['scope'] as String? ?? 'none',
      mode: json['mode'] as String? ?? 'safe_auto',
      allowedAutoStatuses:
          (json['allowed_auto_statuses'] as List<dynamic>? ?? [])
              .whereType<String>()
              .toList(),
      highRiskRequiresReview:
          json['high_risk_requires_review'] as bool? ?? true,
      assigneeChangeRequiresReview:
          json['assignee_change_requires_review'] as bool? ?? true,
      conflictRequiresReview: json['conflict_requires_review'] as bool? ?? true,
      updatedAt: json['updated_at'] as String?,
    );
  }
}

class PromiseAutomationPolicyUpdateRequest {
  final String mode;
  final List<String> allowedAutoStatuses;
  final bool highRiskRequiresReview;
  final bool assigneeChangeRequiresReview;
  final bool conflictRequiresReview;

  const PromiseAutomationPolicyUpdateRequest({
    this.mode = 'safe_auto',
    this.allowedAutoStatuses = const [],
    this.highRiskRequiresReview = true,
    this.assigneeChangeRequiresReview = true,
    this.conflictRequiresReview = true,
  });

  Map<String, dynamic> toJson() {
    return {
      'mode': mode,
      'allowed_auto_statuses': allowedAutoStatuses,
      'high_risk_requires_review': highRiskRequiresReview,
      'assignee_change_requires_review': assigneeChangeRequiresReview,
      'conflict_requires_review': conflictRequiresReview,
    };
  }
}

class PromiseCalendarExportResponse {
  final String ledgerEntryId;
  final String title;
  final String? dueAt;
  final String icsFilename;
  final String icsContent;
  final String googleCalendarUrl;
  final Map<String, dynamic>? calendarEvent;

  const PromiseCalendarExportResponse({
    required this.ledgerEntryId,
    required this.title,
    this.dueAt,
    required this.icsFilename,
    required this.icsContent,
    required this.googleCalendarUrl,
    this.calendarEvent,
  });

  factory PromiseCalendarExportResponse.fromJson(Map<String, dynamic> json) {
    return PromiseCalendarExportResponse(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      dueAt: json['due_at'] as String?,
      icsFilename: json['ics_filename'] as String? ?? '',
      icsContent: json['ics_content'] as String? ?? '',
      googleCalendarUrl: json['google_calendar_url'] as String? ?? '',
      calendarEvent: json['calendar_event'] as Map<String, dynamic>?,
    );
  }
}

class PromiseLearningFeedbackRequest {
  final String? expectedStatus;
  final String? predictedStatus;
  final String? expectedAssignedUserId;
  final String? expectedOwner;
  final String correctionType;
  final String? note;

  const PromiseLearningFeedbackRequest({
    this.expectedStatus,
    this.predictedStatus,
    this.expectedAssignedUserId,
    this.expectedOwner,
    this.correctionType = 'status',
    this.note,
  });

  Map<String, dynamic> toJson() {
    return {
      if (expectedStatus != null) 'expected_status': expectedStatus,
      if (predictedStatus != null) 'predicted_status': predictedStatus,
      if (expectedAssignedUserId != null)
        'expected_assigned_user_id': expectedAssignedUserId,
      if (expectedOwner != null) 'expected_owner': expectedOwner,
      'correction_type': correctionType,
      if (note != null) 'note': note,
    };
  }
}

class PromiseLearningProfile {
  final String scope;
  final double autopilotThreshold;
  final Map<String, double> statusThresholds;
  final int falsePositiveCount;
  final int confirmedCount;
  final Map<String, int> statusFalsePositiveCount;
  final Map<String, int> statusConfirmedCount;
  final int assigneeCorrectionCount;
  final bool evidenceLockEnabled;
  final Map<String, String> learnedOwnerAliases;
  final List<PromiseOwnerAlias> ownerAliases;

  const PromiseLearningProfile({
    required this.scope,
    required this.autopilotThreshold,
    this.statusThresholds = const {},
    required this.falsePositiveCount,
    required this.confirmedCount,
    this.statusFalsePositiveCount = const {},
    this.statusConfirmedCount = const {},
    required this.assigneeCorrectionCount,
    required this.evidenceLockEnabled,
    required this.learnedOwnerAliases,
    this.ownerAliases = const [],
  });

  factory PromiseLearningProfile.fromJson(Map<String, dynamic> json) {
    return PromiseLearningProfile(
      scope: json['scope'] as String? ?? 'none',
      autopilotThreshold:
          (json['autopilot_threshold'] as num?)?.toDouble() ?? 0.68,
      statusThresholds:
          (json['status_thresholds'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toDouble() ?? 0.68),
      ),
      falsePositiveCount: json['false_positive_count'] as int? ?? 0,
      confirmedCount: json['confirmed_count'] as int? ?? 0,
      statusFalsePositiveCount: (json['status_false_positive_count']
                  as Map<String, dynamic>? ??
              {})
          .map((key, value) => MapEntry(key, (value as num?)?.toInt() ?? 0)),
      statusConfirmedCount:
          (json['status_confirmed_count'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toInt() ?? 0),
      ),
      assigneeCorrectionCount: json['assignee_correction_count'] as int? ?? 0,
      evidenceLockEnabled: json['evidence_lock_enabled'] as bool? ?? true,
      learnedOwnerAliases:
          (json['learned_owner_aliases'] as Map<String, dynamic>? ?? {})
              .map((key, value) => MapEntry(key, value.toString())),
      ownerAliases: (json['owner_aliases'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseOwnerAlias.fromJson)
          .toList(),
    );
  }
}

class PromiseLearningFeedbackResponse {
  final String ledgerEntryId;
  final bool recorded;
  final PromiseLearningProfile learningProfile;

  const PromiseLearningFeedbackResponse({
    required this.ledgerEntryId,
    required this.recorded,
    required this.learningProfile,
  });

  factory PromiseLearningFeedbackResponse.fromJson(Map<String, dynamic> json) {
    return PromiseLearningFeedbackResponse(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      recorded: json['recorded'] as bool? ?? false,
      learningProfile: PromiseLearningProfile.fromJson(
        json['learning_profile'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
    );
  }
}

class PromiseTimelineItem {
  final String id;
  final String eventType;
  final String label;
  final String createdAt;
  final String? actorUserId;
  final String? statusBefore;
  final String? statusAfter;
  final double? confidence;
  final String? sourceTaskId;
  final String? note;

  const PromiseTimelineItem({
    required this.id,
    required this.eventType,
    required this.label,
    required this.createdAt,
    this.actorUserId,
    this.statusBefore,
    this.statusAfter,
    this.confidence,
    this.sourceTaskId,
    this.note,
  });

  factory PromiseTimelineItem.fromJson(Map<String, dynamic> json) {
    return PromiseTimelineItem(
      id: json['id'] as String? ?? '',
      eventType: json['event_type'] as String? ?? '',
      label: json['label'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
      actorUserId: json['actor_user_id'] as String?,
      statusBefore: json['status_before'] as String?,
      statusAfter: json['status_after'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      sourceTaskId: json['source_task_id'] as String?,
      note: json['note'] as String?,
    );
  }
}

class PromiseTimelineResponse {
  final String ledgerEntryId;
  final String currentStatus;
  final List<PromiseTimelineItem> items;

  const PromiseTimelineResponse({
    required this.ledgerEntryId,
    required this.currentStatus,
    required this.items,
  });

  factory PromiseTimelineResponse.fromJson(Map<String, dynamic> json) {
    return PromiseTimelineResponse(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      currentStatus: json['current_status'] as String? ?? '',
      items: (json['items'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseTimelineItem.fromJson)
          .toList(),
    );
  }
}

class PromisePreMeetingBrief {
  final String title;
  final int readinessScore;
  final String summary;
  final List<PromiseLedgerEntry> promises;
  final List<String> questions;

  const PromisePreMeetingBrief({
    required this.title,
    required this.readinessScore,
    required this.summary,
    required this.promises,
    required this.questions,
  });

  factory PromisePreMeetingBrief.fromJson(Map<String, dynamic> json) {
    return PromisePreMeetingBrief(
      title: json['title'] as String? ?? '회의 시작 전 약속 브리프',
      readinessScore: json['readiness_score'] as int? ?? 100,
      summary: json['summary'] as String? ?? '',
      promises: (json['promises'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseLedgerEntry.fromJson)
          .toList(),
      questions: (json['questions'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseDigest {
  final String cadence;
  final String title;
  final String generatedAt;
  final int openCount;
  final int overdueCount;
  final int dueSoonCount;
  final int highRiskCount;
  final List<String> lines;
  final List<PromiseLedgerEntry> promises;

  const PromiseDigest({
    required this.cadence,
    required this.title,
    required this.generatedAt,
    required this.openCount,
    required this.overdueCount,
    required this.dueSoonCount,
    required this.highRiskCount,
    required this.lines,
    required this.promises,
  });

  factory PromiseDigest.fromJson(Map<String, dynamic> json) {
    return PromiseDigest(
      cadence: json['cadence'] as String? ?? 'daily',
      title: json['title'] as String? ?? '오늘의 약속 레이더',
      generatedAt: json['generated_at'] as String? ?? '',
      openCount: json['open_count'] as int? ?? 0,
      overdueCount: json['overdue_count'] as int? ?? 0,
      dueSoonCount: json['due_soon_count'] as int? ?? 0,
      highRiskCount: json['high_risk_count'] as int? ?? 0,
      lines:
          (json['lines'] as List<dynamic>? ?? []).whereType<String>().toList(),
      promises: (json['promises'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseLedgerEntry.fromJson)
          .toList(),
    );
  }
}

class PromiseExternalExportRequest {
  final String provider;
  final bool dryRun;
  final String? accessToken;
  final String tasklist;
  final String? parentTaskId;
  final String? previousTaskId;

  const PromiseExternalExportRequest({
    this.provider = 'slack',
    this.dryRun = true,
    this.accessToken,
    this.tasklist = '@default',
    this.parentTaskId,
    this.previousTaskId,
  });

  Map<String, dynamic> toJson() {
    return {
      'provider': provider,
      'dry_run': dryRun,
      if (accessToken != null) 'access_token': accessToken,
      'tasklist': tasklist,
      if (parentTaskId != null) 'parent_task_id': parentTaskId,
      if (previousTaskId != null) 'previous_task_id': previousTaskId,
    };
  }
}

class PromiseExternalExportResponse {
  final String ledgerEntryId;
  final String provider;
  final bool sent;
  final Map<String, dynamic> payload;
  final String message;
  final String? externalId;
  final String? externalUrl;

  const PromiseExternalExportResponse({
    required this.ledgerEntryId,
    required this.provider,
    required this.sent,
    required this.payload,
    required this.message,
    this.externalId,
    this.externalUrl,
  });

  factory PromiseExternalExportResponse.fromJson(Map<String, dynamic> json) {
    return PromiseExternalExportResponse(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      provider: json['provider'] as String? ?? 'slack',
      sent: json['sent'] as bool? ?? false,
      payload:
          json['payload'] as Map<String, dynamic>? ?? const <String, dynamic>{},
      message: json['message'] as String? ?? '',
      externalId: json['external_id'] as String?,
      externalUrl: json['external_url'] as String?,
    );
  }
}

class PromiseAccuracyCase {
  final String id;
  final String entryText;
  final String currentText;
  final String expectedStatus;
  final String? owner;
  final DateTime? dueAt;

  const PromiseAccuracyCase({
    required this.id,
    required this.entryText,
    required this.currentText,
    required this.expectedStatus,
    this.owner,
    this.dueAt,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'entry_text': entryText,
      'current_text': currentText,
      'expected_status': expectedStatus,
      if (owner != null) 'owner': owner,
      if (dueAt != null) 'due_at': dueAt!.toIso8601String(),
    };
  }
}

class PromiseAccuracyEvaluation {
  final int caseCount;
  final int correctCount;
  final double accuracy;
  final Map<String, double> statusPrecision;
  final List<Map<String, dynamic>> failures;

  const PromiseAccuracyEvaluation({
    required this.caseCount,
    required this.correctCount,
    required this.accuracy,
    required this.statusPrecision,
    required this.failures,
  });

  factory PromiseAccuracyEvaluation.fromJson(Map<String, dynamic> json) {
    return PromiseAccuracyEvaluation(
      caseCount: json['case_count'] as int? ?? 0,
      correctCount: json['correct_count'] as int? ?? 0,
      accuracy: (json['accuracy'] as num?)?.toDouble() ?? 0,
      statusPrecision:
          (json['status_precision'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toDouble() ?? 0),
      ),
      failures: (json['failures'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .toList(),
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
  final PromiseQualityScore? quality;
  final List<PromiseAssigneeSuggestion> assigneeSuggestions;

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
    this.quality,
    this.assigneeSuggestions = const [],
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
      quality: json['quality'] is Map<String, dynamic>
          ? PromiseQualityScore.fromJson(
              json['quality'] as Map<String, dynamic>)
          : null,
      assigneeSuggestions:
          (json['assignee_suggestions'] as List<dynamic>? ?? [])
              .whereType<Map<String, dynamic>>()
              .map(PromiseAssigneeSuggestion.fromJson)
              .toList(),
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
  final List<PromiseAutopilotAssessment> autopilotAssessments;
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
    this.autopilotAssessments = const [],
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
      autopilotAssessments:
          (json['autopilot_assessments'] as List<dynamic>? ?? [])
              .whereType<Map<String, dynamic>>()
              .map(PromiseAutopilotAssessment.fromJson)
              .toList(),
      semanticEnrichmentStatus:
          json['semantic_enrichment_status'] as String? ?? 'deterministic',
      followUpQuestions: (json['follow_up_questions'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}
