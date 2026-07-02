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

class PromiseEvidenceComparison {
  final String ledgerEntryId;
  final String? previousText;
  final String? currentText;
  final double? previousSimilarity;
  final double? currentSimilarity;
  final double? similarityDelta;
  final List<String> sharedTerms;
  final List<PromiseRadarEvidence> previousEvidence;
  final PromiseEvidencePack? currentPack;
  final String summary;

  const PromiseEvidenceComparison({
    required this.ledgerEntryId,
    this.previousText,
    this.currentText,
    this.previousSimilarity,
    this.currentSimilarity,
    this.similarityDelta,
    required this.sharedTerms,
    required this.previousEvidence,
    this.currentPack,
    required this.summary,
  });

  factory PromiseEvidenceComparison.fromJson(Map<String, dynamic> json) {
    return PromiseEvidenceComparison(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      previousText: json['previous_text'] as String?,
      currentText: json['current_text'] as String?,
      previousSimilarity: (json['previous_similarity'] as num?)?.toDouble(),
      currentSimilarity: (json['current_similarity'] as num?)?.toDouble(),
      similarityDelta: (json['similarity_delta'] as num?)?.toDouble(),
      sharedTerms: (json['shared_terms'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      previousEvidence: (json['previous_evidence'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseRadarEvidence.fromJson)
          .toList(),
      currentPack: json['current_pack'] is Map<String, dynamic>
          ? PromiseEvidencePack.fromJson(
              json['current_pack'] as Map<String, dynamic>,
            )
          : null,
      summary: json['summary'] as String? ?? '',
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
    this.mode = 'preview_only',
    this.allowedAutoStatuses = const [],
    this.highRiskRequiresReview = true,
    this.assigneeChangeRequiresReview = true,
    this.conflictRequiresReview = true,
    this.updatedAt,
  });

  factory PromiseAutomationPolicy.fromJson(Map<String, dynamic> json) {
    return PromiseAutomationPolicy(
      scope: json['scope'] as String? ?? 'none',
      mode: json['mode'] as String? ?? 'preview_only',
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
    this.mode = 'preview_only',
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

class PromiseLearningInsight {
  final String scope;
  final double autopilotThreshold;
  final Map<String, double> statusThresholds;
  final Map<String, int> statusSampleCounts;
  final Map<String, double> statusFalsePositiveRate;
  final int feedbackCount;
  final int productionSignalCount;
  final int hardNegativeCount;
  final int falsePositiveCount;
  final int confirmedCount;
  final int assigneeCorrectionCount;
  final int aliasGraphSize;
  final int ownerIdentityReviewCount;
  final Map<String, int> scopeBreakdown;
  final List<String> scopeRecommendations;
  final bool evidenceLockEnabled;
  final List<String> statusAttention;
  final String recommendedPolicy;
  final List<String> insights;
  final List<String> nextActions;

  const PromiseLearningInsight({
    required this.scope,
    required this.autopilotThreshold,
    required this.statusThresholds,
    this.statusSampleCounts = const {},
    this.statusFalsePositiveRate = const {},
    required this.feedbackCount,
    this.productionSignalCount = 0,
    this.hardNegativeCount = 0,
    required this.falsePositiveCount,
    required this.confirmedCount,
    required this.assigneeCorrectionCount,
    this.aliasGraphSize = 0,
    this.ownerIdentityReviewCount = 0,
    this.scopeBreakdown = const {},
    this.scopeRecommendations = const [],
    this.evidenceLockEnabled = true,
    required this.statusAttention,
    required this.recommendedPolicy,
    required this.insights,
    required this.nextActions,
  });

  factory PromiseLearningInsight.fromJson(Map<String, dynamic> json) {
    return PromiseLearningInsight(
      scope: json['scope'] as String? ?? 'none',
      autopilotThreshold:
          (json['autopilot_threshold'] as num?)?.toDouble() ?? 0.68,
      statusThresholds:
          (json['status_thresholds'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toDouble() ?? 0.68),
      ),
      statusSampleCounts:
          (json['status_sample_counts'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toInt() ?? 0),
      ),
      statusFalsePositiveRate:
          (json['status_false_positive_rate'] as Map<String, dynamic>? ?? {})
              .map(
        (key, value) => MapEntry(key, (value as num?)?.toDouble() ?? 0),
      ),
      feedbackCount: json['feedback_count'] as int? ?? 0,
      productionSignalCount: json['production_signal_count'] as int? ?? 0,
      hardNegativeCount: json['hard_negative_count'] as int? ?? 0,
      falsePositiveCount: json['false_positive_count'] as int? ?? 0,
      confirmedCount: json['confirmed_count'] as int? ?? 0,
      assigneeCorrectionCount: json['assignee_correction_count'] as int? ?? 0,
      aliasGraphSize: json['alias_graph_size'] as int? ?? 0,
      ownerIdentityReviewCount:
          json['owner_identity_review_count'] as int? ?? 0,
      scopeBreakdown:
          (json['scope_breakdown'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toInt() ?? 0),
      ),
      scopeRecommendations:
          (json['scope_recommendations'] as List<dynamic>? ?? [])
              .whereType<String>()
              .toList(),
      evidenceLockEnabled: json['evidence_lock_enabled'] as bool? ?? true,
      statusAttention: (json['status_attention'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      recommendedPolicy:
          json['recommended_policy'] as String? ?? 'preview_only',
      insights: (json['insights'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      nextActions: (json['next_actions'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseLearningTelemetrySegment {
  final String dimension;
  final String value;
  final int sampleCount;
  final int confirmedCount;
  final int falsePositiveCount;
  final int correctionCount;
  final double precision;
  final double falsePositiveRate;
  final List<String> notes;

  const PromiseLearningTelemetrySegment({
    required this.dimension,
    required this.value,
    required this.sampleCount,
    required this.confirmedCount,
    required this.falsePositiveCount,
    required this.correctionCount,
    required this.precision,
    required this.falsePositiveRate,
    required this.notes,
  });

  factory PromiseLearningTelemetrySegment.fromJson(Map<String, dynamic> json) {
    return PromiseLearningTelemetrySegment(
      dimension: json['dimension'] as String? ?? '',
      value: json['value'] as String? ?? '',
      sampleCount: json['sample_count'] as int? ?? 0,
      confirmedCount: json['confirmed_count'] as int? ?? 0,
      falsePositiveCount: json['false_positive_count'] as int? ?? 0,
      correctionCount: json['correction_count'] as int? ?? 0,
      precision: (json['precision'] as num?)?.toDouble() ?? 0,
      falsePositiveRate: (json['false_positive_rate'] as num?)?.toDouble() ?? 0,
      notes:
          (json['notes'] as List<dynamic>? ?? []).whereType<String>().toList(),
    );
  }
}

class PromiseLearningTelemetryReport {
  final String generatedAt;
  final String scope;
  final int eventCount;
  final int feedbackEventCount;
  final List<PromiseLearningTelemetrySegment> statusSegments;
  final List<PromiseLearningTelemetrySegment> ownerSegments;
  final List<PromiseLearningTelemetrySegment> localeSegments;
  final List<PromiseLearningTelemetrySegment> payloadShapeSegments;
  final List<String> recommendations;

  const PromiseLearningTelemetryReport({
    required this.generatedAt,
    required this.scope,
    required this.eventCount,
    required this.feedbackEventCount,
    required this.statusSegments,
    required this.ownerSegments,
    required this.localeSegments,
    required this.payloadShapeSegments,
    required this.recommendations,
  });

  factory PromiseLearningTelemetryReport.fromJson(Map<String, dynamic> json) {
    List<PromiseLearningTelemetrySegment> parseSegments(String key) {
      return (json[key] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseLearningTelemetrySegment.fromJson)
          .toList();
    }

    return PromiseLearningTelemetryReport(
      generatedAt: json['generated_at'] as String? ?? '',
      scope: json['scope'] as String? ?? 'none',
      eventCount: json['event_count'] as int? ?? 0,
      feedbackEventCount: json['feedback_event_count'] as int? ?? 0,
      statusSegments: parseSegments('status_segments'),
      ownerSegments: parseSegments('owner_segments'),
      localeSegments: parseSegments('locale_segments'),
      payloadShapeSegments: parseSegments('payload_shape_segments'),
      recommendations: (json['recommendations'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseAutopilotQuarantineSummary {
  final int quarantinedCount;
  final int rejectedCount;
  final String safeMode;
  final int autoApplyBlockedCount;
  final String? previewOnlyReason;
  final Map<String, int> affectedStatuses;
  final List<String> affectedEntries;
  final List<String> notes;

  const PromiseAutopilotQuarantineSummary({
    required this.quarantinedCount,
    required this.rejectedCount,
    this.safeMode = 'preview_only',
    this.autoApplyBlockedCount = 0,
    this.previewOnlyReason,
    required this.affectedStatuses,
    required this.affectedEntries,
    required this.notes,
  });

  factory PromiseAutopilotQuarantineSummary.fromJson(
      Map<String, dynamic> json) {
    return PromiseAutopilotQuarantineSummary(
      quarantinedCount: json['quarantined_count'] as int? ?? 0,
      rejectedCount: json['rejected_count'] as int? ?? 0,
      safeMode: json['safe_mode'] as String? ?? 'preview_only',
      autoApplyBlockedCount: json['auto_apply_blocked_count'] as int? ?? 0,
      previewOnlyReason: json['preview_only_reason'] as String?,
      affectedStatuses:
          (json['affected_statuses'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toInt() ?? 0),
      ),
      affectedEntries: (json['affected_entries'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      notes:
          (json['notes'] as List<dynamic>? ?? []).whereType<String>().toList(),
    );
  }
}

class PromiseLiveCoachPrompt {
  final String key;
  final String label;
  final String prompt;
  final String severity;
  final String? owner;
  final String? dueAt;
  final String? ledgerEntryId;

  const PromiseLiveCoachPrompt({
    required this.key,
    required this.label,
    required this.prompt,
    required this.severity,
    this.owner,
    this.dueAt,
    this.ledgerEntryId,
  });

  factory PromiseLiveCoachPrompt.fromJson(Map<String, dynamic> json) {
    return PromiseLiveCoachPrompt(
      key: json['key'] as String? ?? '',
      label: json['label'] as String? ?? '',
      prompt: json['prompt'] as String? ?? '',
      severity: json['severity'] as String? ?? 'info',
      owner: json['owner'] as String?,
      dueAt: json['due_at'] as String?,
      ledgerEntryId: json['ledger_entry_id'] as String?,
    );
  }
}

class PromiseLiveCoachSummary {
  final String generatedAt;
  final int readinessScore;
  final int promptCount;
  final bool recordingSurfaceReady;
  final int slaRiskCount;
  final List<PromiseLiveCoachPrompt> prompts;
  final List<String> notes;

  const PromiseLiveCoachSummary({
    required this.generatedAt,
    required this.readinessScore,
    required this.promptCount,
    this.recordingSurfaceReady = true,
    this.slaRiskCount = 0,
    required this.prompts,
    required this.notes,
  });

  factory PromiseLiveCoachSummary.fromJson(Map<String, dynamic> json) {
    return PromiseLiveCoachSummary(
      generatedAt: json['generated_at'] as String? ?? '',
      readinessScore: json['readiness_score'] as int? ?? 0,
      promptCount: json['prompt_count'] as int? ?? 0,
      recordingSurfaceReady: json['recording_surface_ready'] as bool? ?? true,
      slaRiskCount: json['sla_risk_count'] as int? ?? 0,
      prompts: (json['prompts'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseLiveCoachPrompt.fromJson)
          .toList(),
      notes:
          (json['notes'] as List<dynamic>? ?? []).whereType<String>().toList(),
    );
  }
}

class PromiseEvidenceRoomSummary {
  final String scope;
  final int shareReadyCount;
  final int redactionRequiredCount;
  final int blockedCount;
  final int defaultTtlHours;
  final int maxTtlHours;
  final bool requiresAuthentication;
  final bool auditLogEnabled;
  final String sharePolicyVersion;
  final List<String> policyNotes;

  const PromiseEvidenceRoomSummary({
    required this.scope,
    required this.shareReadyCount,
    required this.redactionRequiredCount,
    required this.blockedCount,
    required this.defaultTtlHours,
    this.maxTtlHours = 168,
    this.requiresAuthentication = true,
    this.auditLogEnabled = true,
    this.sharePolicyVersion = 'v19',
    required this.policyNotes,
  });

  factory PromiseEvidenceRoomSummary.fromJson(Map<String, dynamic> json) {
    return PromiseEvidenceRoomSummary(
      scope: json['scope'] as String? ?? 'none',
      shareReadyCount: json['share_ready_count'] as int? ?? 0,
      redactionRequiredCount: json['redaction_required_count'] as int? ?? 0,
      blockedCount: json['blocked_count'] as int? ?? 0,
      defaultTtlHours: json['default_ttl_hours'] as int? ?? 72,
      maxTtlHours: json['max_ttl_hours'] as int? ?? 168,
      requiresAuthentication: json['requires_authentication'] as bool? ?? true,
      auditLogEnabled: json['audit_log_enabled'] as bool? ?? true,
      sharePolicyVersion: json['share_policy_version'] as String? ?? 'v19',
      policyNotes: (json['policy_notes'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseMeetingRecipePolicy {
  final String recipeKey;
  final String label;
  final bool ownerRequired;
  final bool dueDateRequired;
  final String defaultAutopilotMode;
  final List<String> highRiskKeywords;
  final List<String> promptTemplates;
  final List<String> recommendedIntegrations;

  const PromiseMeetingRecipePolicy({
    required this.recipeKey,
    required this.label,
    required this.ownerRequired,
    required this.dueDateRequired,
    required this.defaultAutopilotMode,
    required this.highRiskKeywords,
    required this.promptTemplates,
    required this.recommendedIntegrations,
  });

  factory PromiseMeetingRecipePolicy.fromJson(Map<String, dynamic> json) {
    return PromiseMeetingRecipePolicy(
      recipeKey: json['recipe_key'] as String? ?? 'team_sync',
      label: json['label'] as String? ?? 'Team Sync',
      ownerRequired: json['owner_required'] as bool? ?? true,
      dueDateRequired: json['due_date_required'] as bool? ?? true,
      defaultAutopilotMode:
          json['default_autopilot_mode'] as String? ?? 'preview_only',
      highRiskKeywords: (json['high_risk_keywords'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      promptTemplates: (json['prompt_templates'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      recommendedIntegrations:
          (json['recommended_integrations'] as List<dynamic>? ?? [])
              .whereType<String>()
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
  final List<String> checkpoints;

  const PromisePreMeetingBrief({
    required this.title,
    required this.readinessScore,
    required this.summary,
    required this.promises,
    required this.questions,
    this.checkpoints = const [],
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
      checkpoints: (json['checkpoints'] as List<dynamic>? ?? [])
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
  final int slaDueTodayCount;
  final bool pushReady;
  final String? nextPushLocalTime;
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
    this.slaDueTodayCount = 0,
    this.pushReady = true,
    this.nextPushLocalTime,
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
      slaDueTodayCount: json['sla_due_today_count'] as int? ?? 0,
      pushReady: json['push_ready'] as bool? ?? true,
      nextPushLocalTime: json['next_push_local_time'] as String?,
      lines:
          (json['lines'] as List<dynamic>? ?? []).whereType<String>().toList(),
      promises: (json['promises'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseLedgerEntry.fromJson)
          .toList(),
    );
  }
}

class PromiseDigestPreference {
  final String scope;
  final bool enabled;
  final String cadence;
  final String localTime;
  final String timezone;
  final String? quietHoursStart;
  final String? quietHoursEnd;
  final String? updatedAt;

  const PromiseDigestPreference({
    required this.scope,
    required this.enabled,
    required this.cadence,
    required this.localTime,
    required this.timezone,
    this.quietHoursStart,
    this.quietHoursEnd,
    this.updatedAt,
  });

  factory PromiseDigestPreference.fromJson(Map<String, dynamic> json) {
    return PromiseDigestPreference(
      scope: json['scope'] as String? ?? 'none',
      enabled: json['enabled'] as bool? ?? false,
      cadence: json['cadence'] as String? ?? 'daily',
      localTime: json['local_time'] as String? ?? '08:30',
      timezone: json['timezone'] as String? ?? 'Asia/Seoul',
      quietHoursStart: json['quiet_hours_start'] as String?,
      quietHoursEnd: json['quiet_hours_end'] as String?,
      updatedAt: json['updated_at'] as String?,
    );
  }
}

class PromiseDigestPreferenceUpdateRequest {
  final bool enabled;
  final String cadence;
  final String localTime;
  final String timezone;
  final String? quietHoursStart;
  final String? quietHoursEnd;

  const PromiseDigestPreferenceUpdateRequest({
    this.enabled = false,
    this.cadence = 'daily',
    this.localTime = '08:30',
    this.timezone = 'Asia/Seoul',
    this.quietHoursStart = '22:00',
    this.quietHoursEnd = '07:00',
  });

  Map<String, dynamic> toJson() {
    return {
      'enabled': enabled,
      'cadence': cadence,
      'local_time': localTime,
      'timezone': timezone,
      if (quietHoursStart != null) 'quiet_hours_start': quietHoursStart,
      if (quietHoursEnd != null) 'quiet_hours_end': quietHoursEnd,
    };
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

class PromiseGoogleTaskList {
  final String id;
  final String title;
  final String? updated;

  const PromiseGoogleTaskList({
    required this.id,
    required this.title,
    this.updated,
  });

  factory PromiseGoogleTaskList.fromJson(Map<String, dynamic> json) {
    return PromiseGoogleTaskList(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? 'Untitled',
      updated: json['updated'] as String?,
    );
  }
}

class PromiseGoogleTaskListResponse {
  final List<PromiseGoogleTaskList> tasklists;

  const PromiseGoogleTaskListResponse({required this.tasklists});

  factory PromiseGoogleTaskListResponse.fromJson(Map<String, dynamic> json) {
    return PromiseGoogleTaskListResponse(
      tasklists: (json['tasklists'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseGoogleTaskList.fromJson)
          .toList(),
    );
  }
}

class PromiseExternalTaskSyncRequest {
  final String provider;
  final String? accessToken;
  final String tasklist;
  final String? externalId;

  const PromiseExternalTaskSyncRequest({
    this.provider = 'google_tasks',
    this.accessToken,
    this.tasklist = '@default',
    this.externalId,
  });

  Map<String, dynamic> toJson() {
    return {
      'provider': provider,
      if (accessToken != null) 'access_token': accessToken,
      'tasklist': tasklist,
      if (externalId != null) 'external_id': externalId,
    };
  }
}

class PromiseExternalTaskUpdateRequest {
  final String provider;
  final String? accessToken;
  final String tasklist;
  final String? externalId;
  final String? status;
  final String? title;

  const PromiseExternalTaskUpdateRequest({
    this.provider = 'google_tasks',
    this.accessToken,
    this.tasklist = '@default',
    this.externalId,
    this.status,
    this.title,
  });

  Map<String, dynamic> toJson() {
    return {
      'provider': provider,
      if (accessToken != null) 'access_token': accessToken,
      'tasklist': tasklist,
      if (externalId != null) 'external_id': externalId,
      if (status != null) 'status': status,
      if (title != null) 'title': title,
    };
  }
}

class PromiseExternalTaskSyncResponse {
  final String ledgerEntryId;
  final String provider;
  final bool synced;
  final String? status;
  final String message;
  final Map<String, dynamic>? syncContract;

  const PromiseExternalTaskSyncResponse({
    required this.ledgerEntryId,
    required this.provider,
    required this.synced,
    this.status,
    required this.message,
    this.syncContract,
  });

  factory PromiseExternalTaskSyncResponse.fromJson(Map<String, dynamic> json) {
    return PromiseExternalTaskSyncResponse(
      ledgerEntryId: json['ledger_entry_id'] as String? ?? '',
      provider: json['provider'] as String? ?? 'google_tasks',
      synced: json['synced'] as bool? ?? false,
      status: json['status'] as String?,
      message: json['message'] as String? ?? '',
      syncContract: json['sync_contract'] is Map<String, dynamic>
          ? json['sync_contract'] as Map<String, dynamic>
          : null,
    );
  }
}

class PromiseExternalTaskReconcileItem {
  final PromiseLedgerEntry ledgerEntry;
  final String provider;
  final String? tasklist;
  final String? externalId;
  final String? externalUrl;
  final String ledgerStatus;
  final String? externalStatus;
  final bool needsSync;
  final String direction;
  final String? issue;
  final Map<String, dynamic>? syncContract;

  const PromiseExternalTaskReconcileItem({
    required this.ledgerEntry,
    required this.provider,
    this.tasklist,
    this.externalId,
    this.externalUrl,
    required this.ledgerStatus,
    this.externalStatus,
    required this.needsSync,
    required this.direction,
    this.issue,
    this.syncContract,
  });

  factory PromiseExternalTaskReconcileItem.fromJson(Map<String, dynamic> json) {
    return PromiseExternalTaskReconcileItem(
      ledgerEntry: PromiseLedgerEntry.fromJson(
        json['ledger_entry'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      provider: json['provider'] as String? ?? 'google_tasks',
      tasklist: json['tasklist'] as String?,
      externalId: json['external_id'] as String?,
      externalUrl: json['external_url'] as String?,
      ledgerStatus: json['ledger_status'] as String? ?? '',
      externalStatus: json['external_status'] as String?,
      needsSync: json['needs_sync'] as bool? ?? false,
      direction: json['direction'] as String? ?? 'none',
      issue: json['issue'] as String?,
      syncContract: json['sync_contract'] is Map<String, dynamic>
          ? json['sync_contract'] as Map<String, dynamic>
          : null,
    );
  }
}

class PromiseExternalTaskReconcileResponse {
  final String provider;
  final int checkedCount;
  final int linkedCount;
  final int needsSyncCount;
  final bool requiresOauth;
  final List<PromiseExternalTaskReconcileItem> items;

  const PromiseExternalTaskReconcileResponse({
    required this.provider,
    required this.checkedCount,
    required this.linkedCount,
    required this.needsSyncCount,
    required this.requiresOauth,
    required this.items,
  });

  factory PromiseExternalTaskReconcileResponse.fromJson(
    Map<String, dynamic> json,
  ) {
    return PromiseExternalTaskReconcileResponse(
      provider: json['provider'] as String? ?? 'google_tasks',
      checkedCount: json['checked_count'] as int? ?? 0,
      linkedCount: json['linked_count'] as int? ?? 0,
      needsSyncCount: json['needs_sync_count'] as int? ?? 0,
      requiresOauth: json['requires_oauth'] as bool? ?? true,
      items: (json['items'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseExternalTaskReconcileItem.fromJson)
          .toList(),
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
  final Map<String, Map<String, dynamic>> confidenceBuckets;
  final List<Map<String, dynamic>> failures;

  const PromiseAccuracyEvaluation({
    required this.caseCount,
    required this.correctCount,
    required this.accuracy,
    required this.statusPrecision,
    required this.confidenceBuckets,
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
      confidenceBuckets:
          (json['confidence_buckets'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(
          key,
          value is Map<String, dynamic> ? value : <String, dynamic>{},
        ),
      ),
      failures: (json['failures'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .toList(),
    );
  }
}

class PromiseAccuracyReport {
  final String generatedAt;
  final String fixturePath;
  final String? sourceManifestPath;
  final PromiseAccuracyEvaluation evaluation;
  final Map<String, int> statusCounts;
  final Map<String, int> sourceCounts;
  final Map<String, double> coverage;
  final Map<String, Map<String, dynamic>> sourceQuality;
  final List<String> qualityWarnings;
  final int realMeetingCaseCount;
  final int hardNegativeCaseCount;
  final int publicSourceCount;
  final int targetCaseCount;
  final bool belowTarget;

  const PromiseAccuracyReport({
    required this.generatedAt,
    required this.fixturePath,
    this.sourceManifestPath,
    required this.evaluation,
    required this.statusCounts,
    required this.sourceCounts,
    required this.coverage,
    required this.sourceQuality,
    required this.qualityWarnings,
    required this.realMeetingCaseCount,
    this.hardNegativeCaseCount = 0,
    this.publicSourceCount = 0,
    required this.targetCaseCount,
    required this.belowTarget,
  });

  factory PromiseAccuracyReport.fromJson(Map<String, dynamic> json) {
    return PromiseAccuracyReport(
      generatedAt: json['generated_at'] as String? ?? '',
      fixturePath: json['fixture_path'] as String? ?? '',
      sourceManifestPath: json['source_manifest_path'] as String?,
      evaluation: PromiseAccuracyEvaluation.fromJson(
        json['evaluation'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      statusCounts: (json['status_counts'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toInt() ?? 0),
      ),
      sourceCounts: (json['source_counts'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toInt() ?? 0),
      ),
      coverage: (json['coverage'] as Map<String, dynamic>? ?? {}).map(
        (key, value) => MapEntry(key, (value as num?)?.toDouble() ?? 0),
      ),
      sourceQuality: (json['source_quality'] as Map? ?? {}).map(
        (key, value) => MapEntry(
          key.toString(),
          value is Map
              ? value.map(
                  (nestedKey, nestedValue) =>
                      MapEntry(nestedKey.toString(), nestedValue),
                )
              : <String, dynamic>{},
        ),
      ),
      qualityWarnings: (json['quality_warnings'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      realMeetingCaseCount: json['real_meeting_case_count'] as int? ?? 0,
      hardNegativeCaseCount: json['hard_negative_case_count'] as int? ?? 0,
      publicSourceCount: json['public_source_count'] as int? ?? 0,
      targetCaseCount: json['target_case_count'] as int? ?? 100,
      belowTarget: json['below_target'] as bool? ?? false,
    );
  }
}

class PromiseExtractionRecallEvaluation {
  final int caseCount;
  final int expectedCount;
  final int extractedCount;
  final int matchedCount;
  final double recall;
  final List<Map<String, dynamic>> failures;

  const PromiseExtractionRecallEvaluation({
    required this.caseCount,
    required this.expectedCount,
    required this.extractedCount,
    required this.matchedCount,
    required this.recall,
    required this.failures,
  });

  factory PromiseExtractionRecallEvaluation.fromJson(
    Map<String, dynamic> json,
  ) {
    return PromiseExtractionRecallEvaluation(
      caseCount: json['case_count'] as int? ?? 0,
      expectedCount: json['expected_count'] as int? ?? 0,
      extractedCount: json['extracted_count'] as int? ?? 0,
      matchedCount: json['matched_count'] as int? ?? 0,
      recall: (json['recall'] as num?)?.toDouble() ?? 0,
      failures: (json['failures'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .toList(),
    );
  }
}

class PromiseExtractionRecallReport {
  final String generatedAt;
  final String fixturePath;
  final PromiseExtractionRecallEvaluation evaluation;
  final int realMeetingCaseCount;
  final int targetCaseCount;
  final bool belowTarget;

  const PromiseExtractionRecallReport({
    required this.generatedAt,
    required this.fixturePath,
    required this.evaluation,
    required this.realMeetingCaseCount,
    required this.targetCaseCount,
    required this.belowTarget,
  });

  factory PromiseExtractionRecallReport.fromJson(Map<String, dynamic> json) {
    return PromiseExtractionRecallReport(
      generatedAt: json['generated_at'] as String? ?? '',
      fixturePath: json['fixture_path'] as String? ?? '',
      evaluation: PromiseExtractionRecallEvaluation.fromJson(
        json['evaluation'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      realMeetingCaseCount: json['real_meeting_case_count'] as int? ?? 0,
      targetCaseCount: json['target_case_count'] as int? ?? 50,
      belowTarget: json['below_target'] as bool? ?? false,
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
  final double? identityConfidence;
  final List<String> identityConfidenceFactors;

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
    this.identityConfidence,
    this.identityConfidenceFactors = const [],
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
      identityConfidence: (json['identity_confidence'] as num?)?.toDouble(),
      identityConfidenceFactors:
          (json['identity_confidence_factors'] as List<dynamic>? ?? [])
              .whereType<String>()
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

class PromiseResponsibilityScore {
  final String owner;
  final String? assignedUserId;
  final int score;
  final String riskLevel;
  final int openCount;
  final int completedCount;
  final int delayedCount;
  final int blockedCount;
  final int overdueCount;
  final int dueTodayCount;
  final int slaWatchCount;
  final int escalationCount;
  final int unconfirmedCount;
  final int recurringCount;
  final double completionRate;
  final List<String> reasons;

  const PromiseResponsibilityScore({
    required this.owner,
    this.assignedUserId,
    required this.score,
    required this.riskLevel,
    required this.openCount,
    required this.completedCount,
    required this.delayedCount,
    required this.blockedCount,
    required this.overdueCount,
    this.dueTodayCount = 0,
    this.slaWatchCount = 0,
    this.escalationCount = 0,
    required this.unconfirmedCount,
    required this.recurringCount,
    required this.completionRate,
    required this.reasons,
  });

  factory PromiseResponsibilityScore.fromJson(Map<String, dynamic> json) {
    return PromiseResponsibilityScore(
      owner: json['owner'] as String? ?? '미지정',
      assignedUserId: json['assigned_user_id'] as String?,
      score: json['score'] as int? ?? 0,
      riskLevel: json['risk_level'] as String? ?? 'low',
      openCount: json['open_count'] as int? ?? 0,
      completedCount: json['completed_count'] as int? ?? 0,
      delayedCount: json['delayed_count'] as int? ?? 0,
      blockedCount: json['blocked_count'] as int? ?? 0,
      overdueCount: json['overdue_count'] as int? ?? 0,
      dueTodayCount: json['due_today_count'] as int? ?? 0,
      slaWatchCount: json['sla_watch_count'] as int? ?? 0,
      escalationCount: json['escalation_count'] as int? ?? 0,
      unconfirmedCount: json['unconfirmed_count'] as int? ?? 0,
      recurringCount: json['recurring_count'] as int? ?? 0,
      completionRate: (json['completion_rate'] as num?)?.toDouble() ?? 0,
      reasons: (json['reasons'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseResponsibilityTrendPoint {
  final String periodStart;
  final int score;
  final int openCount;
  final int completedCount;
  final int delayedCount;
  final int blockedCount;
  final int overdueCount;
  final int unconfirmedCount;
  final int recurringCount;

  const PromiseResponsibilityTrendPoint({
    required this.periodStart,
    required this.score,
    required this.openCount,
    required this.completedCount,
    required this.delayedCount,
    required this.blockedCount,
    required this.overdueCount,
    required this.unconfirmedCount,
    required this.recurringCount,
  });

  factory PromiseResponsibilityTrendPoint.fromJson(Map<String, dynamic> json) {
    return PromiseResponsibilityTrendPoint(
      periodStart: json['period_start'] as String? ?? '',
      score: json['score'] as int? ?? 0,
      openCount: json['open_count'] as int? ?? 0,
      completedCount: json['completed_count'] as int? ?? 0,
      delayedCount: json['delayed_count'] as int? ?? 0,
      blockedCount: json['blocked_count'] as int? ?? 0,
      overdueCount: json['overdue_count'] as int? ?? 0,
      unconfirmedCount: json['unconfirmed_count'] as int? ?? 0,
      recurringCount: json['recurring_count'] as int? ?? 0,
    );
  }
}

class PromiseResponsibilityTrend {
  final String owner;
  final String? assignedUserId;
  final int currentScore;
  final String riskLevel;
  final String direction;
  final List<PromiseResponsibilityTrendPoint> points;

  const PromiseResponsibilityTrend({
    required this.owner,
    this.assignedUserId,
    required this.currentScore,
    required this.riskLevel,
    required this.direction,
    required this.points,
  });

  factory PromiseResponsibilityTrend.fromJson(Map<String, dynamic> json) {
    return PromiseResponsibilityTrend(
      owner: json['owner'] as String? ?? '미지정',
      assignedUserId: json['assigned_user_id'] as String?,
      currentScore: json['current_score'] as int? ?? 0,
      riskLevel: json['risk_level'] as String? ?? 'low',
      direction: json['direction'] as String? ?? 'stable',
      points: (json['points'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseResponsibilityTrendPoint.fromJson)
          .toList(),
    );
  }
}

class PromiseMeetingSeries {
  final String seriesKey;
  final String title;
  final int meetingCount;
  final String firstSeenAt;
  final String lastSeenAt;
  final String latestTaskId;
  final int openCount;
  final int overdueCount;
  final int highRiskCount;
  final List<String> owners;
  final List<String> nextQuestions;

  const PromiseMeetingSeries({
    required this.seriesKey,
    required this.title,
    required this.meetingCount,
    required this.firstSeenAt,
    required this.lastSeenAt,
    required this.latestTaskId,
    required this.openCount,
    required this.overdueCount,
    required this.highRiskCount,
    required this.owners,
    required this.nextQuestions,
  });

  factory PromiseMeetingSeries.fromJson(Map<String, dynamic> json) {
    return PromiseMeetingSeries(
      seriesKey: json['series_key'] as String? ?? '',
      title: json['title'] as String? ?? '반복 회의',
      meetingCount: json['meeting_count'] as int? ?? 1,
      firstSeenAt: json['first_seen_at'] as String? ?? '',
      lastSeenAt: json['last_seen_at'] as String? ?? '',
      latestTaskId: json['latest_task_id'] as String? ?? '',
      openCount: json['open_count'] as int? ?? 0,
      overdueCount: json['overdue_count'] as int? ?? 0,
      highRiskCount: json['high_risk_count'] as int? ?? 0,
      owners:
          (json['owners'] as List<dynamic>? ?? []).whereType<String>().toList(),
      nextQuestions: (json['next_questions'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseMeetingSeriesTimelineItem {
  final String seriesKey;
  final String taskId;
  final String title;
  final String seenAt;
  final int openCount;
  final int overdueCount;
  final int highRiskCount;
  final List<String> owners;
  final List<PromiseLedgerEntry> promises;
  final List<String> questions;

  const PromiseMeetingSeriesTimelineItem({
    required this.seriesKey,
    required this.taskId,
    required this.title,
    required this.seenAt,
    required this.openCount,
    required this.overdueCount,
    required this.highRiskCount,
    required this.owners,
    required this.promises,
    required this.questions,
  });

  factory PromiseMeetingSeriesTimelineItem.fromJson(
    Map<String, dynamic> json,
  ) {
    return PromiseMeetingSeriesTimelineItem(
      seriesKey: json['series_key'] as String? ?? '',
      taskId: json['task_id'] as String? ?? '',
      title: json['title'] as String? ?? '반복 회의',
      seenAt: json['seen_at'] as String? ?? '',
      openCount: json['open_count'] as int? ?? 0,
      overdueCount: json['overdue_count'] as int? ?? 0,
      highRiskCount: json['high_risk_count'] as int? ?? 0,
      owners:
          (json['owners'] as List<dynamic>? ?? []).whereType<String>().toList(),
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

class PromiseMeetingSeriesTimeline {
  final String seriesKey;
  final String title;
  final int meetingCount;
  final String? firstSeenAt;
  final String? lastSeenAt;
  final List<PromiseMeetingSeriesTimelineItem> items;

  const PromiseMeetingSeriesTimeline({
    required this.seriesKey,
    required this.title,
    required this.meetingCount,
    this.firstSeenAt,
    this.lastSeenAt,
    required this.items,
  });

  factory PromiseMeetingSeriesTimeline.fromJson(Map<String, dynamic> json) {
    return PromiseMeetingSeriesTimeline(
      seriesKey: json['series_key'] as String? ?? '',
      title: json['title'] as String? ?? '반복 회의',
      meetingCount: json['meeting_count'] as int? ?? 0,
      firstSeenAt: json['first_seen_at'] as String?,
      lastSeenAt: json['last_seen_at'] as String?,
      items: (json['items'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseMeetingSeriesTimelineItem.fromJson)
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
  final List<PromiseResponsibilityScore> responsibilityScores;
  final List<PromiseMeetingSeries> meetingSeries;

  const PromiseNextMeetingBriefing({
    required this.title,
    required this.highRiskCount,
    required this.overdueCount,
    required this.dueSoonCount,
    required this.ownerHotspots,
    required this.promises,
    required this.questions,
    required this.reminderCandidates,
    this.responsibilityScores = const [],
    this.meetingSeries = const [],
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
      responsibilityScores:
          (json['responsibility_scores'] as List<dynamic>? ?? [])
              .whereType<Map<String, dynamic>>()
              .map(PromiseResponsibilityScore.fromJson)
              .toList(),
      meetingSeries: (json['meeting_series'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseMeetingSeries.fromJson)
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
  final List<PromiseResponsibilityScore> responsibilityScores;
  final List<PromiseMeetingSeries> meetingSeries;

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
    this.responsibilityScores = const [],
    this.meetingSeries = const [],
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
      responsibilityScores:
          (json['responsibility_scores'] as List<dynamic>? ?? [])
              .whereType<Map<String, dynamic>>()
              .map(PromiseResponsibilityScore.fromJson)
              .toList(),
      meetingSeries: (json['meeting_series'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseMeetingSeries.fromJson)
          .toList(),
    );
  }
}

class PromiseCommandCenterFocusItem {
  final String key;
  final String label;
  final String severity;
  final int count;
  final String action;
  final String? route;

  const PromiseCommandCenterFocusItem({
    required this.key,
    required this.label,
    required this.severity,
    required this.count,
    required this.action,
    this.route,
  });

  factory PromiseCommandCenterFocusItem.fromJson(Map<String, dynamic> json) {
    return PromiseCommandCenterFocusItem(
      key: json['key'] as String? ?? '',
      label: json['label'] as String? ?? '',
      severity: json['severity'] as String? ?? 'info',
      count: json['count'] as int? ?? 0,
      action: json['action'] as String? ?? '',
      route: json['route'] as String?,
    );
  }
}

class PromiseEvidenceAuditSummary {
  final int lockedCount;
  final int weakEvidenceCount;
  final int missingTimestampCount;
  final int missingSpeakerCount;
  final int markerHitCount;
  final double averageSimilarity;
  final List<String> notes;

  const PromiseEvidenceAuditSummary({
    required this.lockedCount,
    required this.weakEvidenceCount,
    required this.missingTimestampCount,
    required this.missingSpeakerCount,
    required this.markerHitCount,
    required this.averageSimilarity,
    required this.notes,
  });

  factory PromiseEvidenceAuditSummary.fromJson(Map<String, dynamic> json) {
    return PromiseEvidenceAuditSummary(
      lockedCount: json['locked_count'] as int? ?? 0,
      weakEvidenceCount: json['weak_evidence_count'] as int? ?? 0,
      missingTimestampCount: json['missing_timestamp_count'] as int? ?? 0,
      missingSpeakerCount: json['missing_speaker_count'] as int? ?? 0,
      markerHitCount: json['marker_hit_count'] as int? ?? 0,
      averageSimilarity: (json['average_similarity'] as num?)?.toDouble() ?? 0,
      notes:
          (json['notes'] as List<dynamic>? ?? []).whereType<String>().toList(),
    );
  }
}

class PromiseMemoryGraphNode {
  final String id;
  final String label;
  final String kind;
  final int weight;
  final String? status;
  final String? riskLevel;

  const PromiseMemoryGraphNode({
    required this.id,
    required this.label,
    required this.kind,
    required this.weight,
    this.status,
    this.riskLevel,
  });

  factory PromiseMemoryGraphNode.fromJson(Map<String, dynamic> json) {
    return PromiseMemoryGraphNode(
      id: json['id'] as String? ?? '',
      label: json['label'] as String? ?? '',
      kind: json['kind'] as String? ?? '',
      weight: json['weight'] as int? ?? 0,
      status: json['status'] as String?,
      riskLevel: json['risk_level'] as String?,
    );
  }
}

class PromiseMemoryGraphEdge {
  final String source;
  final String target;
  final String relationship;
  final int weight;

  const PromiseMemoryGraphEdge({
    required this.source,
    required this.target,
    required this.relationship,
    required this.weight,
  });

  factory PromiseMemoryGraphEdge.fromJson(Map<String, dynamic> json) {
    return PromiseMemoryGraphEdge(
      source: json['source'] as String? ?? '',
      target: json['target'] as String? ?? '',
      relationship: json['relationship'] as String? ?? '',
      weight: json['weight'] as int? ?? 0,
    );
  }
}

class PromiseMemoryGraph {
  final int nodeCount;
  final int edgeCount;
  final int recurringSeriesCount;
  final int changedClusterCount;
  final int delayedClusterCount;
  final int ownerAliasCount;
  final int identityClusterCount;
  final int ownerAliasReviewCount;
  final List<PromiseMemoryGraphNode> nodes;
  final List<PromiseMemoryGraphEdge> edges;
  final List<String> narrative;

  const PromiseMemoryGraph({
    required this.nodeCount,
    required this.edgeCount,
    required this.recurringSeriesCount,
    required this.changedClusterCount,
    required this.delayedClusterCount,
    required this.ownerAliasCount,
    this.identityClusterCount = 0,
    this.ownerAliasReviewCount = 0,
    required this.nodes,
    required this.edges,
    required this.narrative,
  });

  factory PromiseMemoryGraph.fromJson(Map<String, dynamic> json) {
    return PromiseMemoryGraph(
      nodeCount: json['node_count'] as int? ?? 0,
      edgeCount: json['edge_count'] as int? ?? 0,
      recurringSeriesCount: json['recurring_series_count'] as int? ?? 0,
      changedClusterCount: json['changed_cluster_count'] as int? ?? 0,
      delayedClusterCount: json['delayed_cluster_count'] as int? ?? 0,
      ownerAliasCount: json['owner_alias_count'] as int? ?? 0,
      identityClusterCount: json['identity_cluster_count'] as int? ?? 0,
      ownerAliasReviewCount: json['owner_alias_review_count'] as int? ?? 0,
      nodes: (json['nodes'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseMemoryGraphNode.fromJson)
          .toList(),
      edges: (json['edges'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseMemoryGraphEdge.fromJson)
          .toList(),
      narrative: (json['narrative'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseAutopilotShadowSummary {
  final int candidateCount;
  final int wouldApplyCount;
  final int previewOnlyCount;
  final int blockedByEvidenceCount;
  final int conflictCount;
  final Map<String, int> statusDistribution;
  final double averageConfidence;
  final String learningValue;
  final List<String> notes;

  const PromiseAutopilotShadowSummary({
    required this.candidateCount,
    required this.wouldApplyCount,
    required this.previewOnlyCount,
    required this.blockedByEvidenceCount,
    required this.conflictCount,
    required this.statusDistribution,
    required this.averageConfidence,
    required this.learningValue,
    required this.notes,
  });

  factory PromiseAutopilotShadowSummary.fromJson(Map<String, dynamic> json) {
    return PromiseAutopilotShadowSummary(
      candidateCount: json['candidate_count'] as int? ?? 0,
      wouldApplyCount: json['would_apply_count'] as int? ?? 0,
      previewOnlyCount: json['preview_only_count'] as int? ?? 0,
      blockedByEvidenceCount: json['blocked_by_evidence_count'] as int? ?? 0,
      conflictCount: json['conflict_count'] as int? ?? 0,
      statusDistribution: (json['status_distribution']
                  as Map<String, dynamic>? ??
              const <String, dynamic>{})
          .map((key, value) => MapEntry(key, (value as num?)?.toInt() ?? 0)),
      averageConfidence: (json['average_confidence'] as num?)?.toDouble() ?? 0,
      learningValue: json['learning_value'] as String? ?? '',
      notes:
          (json['notes'] as List<dynamic>? ?? []).whereType<String>().toList(),
    );
  }
}

class PromiseEvidencePermissionSummary {
  final String scope;
  final bool exportAllowed;
  final bool redactionRequired;
  final bool containsSpeakerData;
  final bool containsTimestampData;
  final int allowedEvidenceCount;
  final int blockedExportCount;
  final List<String> policyNotes;

  const PromiseEvidencePermissionSummary({
    required this.scope,
    required this.exportAllowed,
    required this.redactionRequired,
    required this.containsSpeakerData,
    required this.containsTimestampData,
    required this.allowedEvidenceCount,
    required this.blockedExportCount,
    required this.policyNotes,
  });

  factory PromiseEvidencePermissionSummary.fromJson(Map<String, dynamic> json) {
    return PromiseEvidencePermissionSummary(
      scope: json['scope'] as String? ?? '',
      exportAllowed: json['export_allowed'] as bool? ?? false,
      redactionRequired: json['redaction_required'] as bool? ?? false,
      containsSpeakerData: json['contains_speaker_data'] as bool? ?? false,
      containsTimestampData: json['contains_timestamp_data'] as bool? ?? false,
      allowedEvidenceCount: json['allowed_evidence_count'] as int? ?? 0,
      blockedExportCount: json['blocked_export_count'] as int? ?? 0,
      policyNotes: (json['policy_notes'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseTeamScorecard {
  final int riskScore;
  final int ownerCount;
  final int openCount;
  final int overdueCount;
  final int highRiskCount;
  final int dueTodayCount;
  final int slaWatchCount;
  final int escalationCount;
  final int recurringSeriesCount;
  final String? weakestOwner;
  final String? strongestOwner;
  final List<String> recommendations;

  const PromiseTeamScorecard({
    required this.riskScore,
    required this.ownerCount,
    required this.openCount,
    required this.overdueCount,
    required this.highRiskCount,
    this.dueTodayCount = 0,
    this.slaWatchCount = 0,
    this.escalationCount = 0,
    required this.recurringSeriesCount,
    this.weakestOwner,
    this.strongestOwner,
    required this.recommendations,
  });

  factory PromiseTeamScorecard.fromJson(Map<String, dynamic> json) {
    return PromiseTeamScorecard(
      riskScore: json['risk_score'] as int? ?? 0,
      ownerCount: json['owner_count'] as int? ?? 0,
      openCount: json['open_count'] as int? ?? 0,
      overdueCount: json['overdue_count'] as int? ?? 0,
      highRiskCount: json['high_risk_count'] as int? ?? 0,
      dueTodayCount: json['due_today_count'] as int? ?? 0,
      slaWatchCount: json['sla_watch_count'] as int? ?? 0,
      escalationCount: json['escalation_count'] as int? ?? 0,
      recurringSeriesCount: json['recurring_series_count'] as int? ?? 0,
      weakestOwner: json['weakest_owner'] as String?,
      strongestOwner: json['strongest_owner'] as String?,
      recommendations: (json['recommendations'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseGoogleTasksOAuthGuide {
  final String provider;
  final String scope;
  final String authUrlHint;
  final String appRedirectUri;
  final bool redirectUriRequired;
  final bool pkceRequired;
  final bool tasklistSelectionRequired;
  final String callbackPath;
  final bool oauthUxReady;
  final bool tokenExchangeReady;
  final bool productionReady;
  final List<String> missingSetup;
  final List<String> requiredBackendEnv;
  final List<String> verificationSteps;
  final List<String> steps;
  final String tokenHandling;
  final List<String> securityNotes;

  const PromiseGoogleTasksOAuthGuide({
    required this.provider,
    required this.scope,
    required this.authUrlHint,
    required this.appRedirectUri,
    required this.redirectUriRequired,
    this.pkceRequired = true,
    this.tasklistSelectionRequired = true,
    required this.callbackPath,
    this.oauthUxReady = false,
    this.tokenExchangeReady = false,
    required this.productionReady,
    required this.missingSetup,
    required this.requiredBackendEnv,
    required this.verificationSteps,
    required this.steps,
    required this.tokenHandling,
    required this.securityNotes,
  });

  factory PromiseGoogleTasksOAuthGuide.fromJson(Map<String, dynamic> json) {
    return PromiseGoogleTasksOAuthGuide(
      provider: json['provider'] as String? ?? 'google_tasks',
      scope:
          json['scope'] as String? ?? 'https://www.googleapis.com/auth/tasks',
      authUrlHint: json['auth_url_hint'] as String? ?? '',
      appRedirectUri: json['app_redirect_uri'] as String? ??
          'com.voicetextnote.app:/oauth2redirect/google-tasks',
      redirectUriRequired: json['redirect_uri_required'] as bool? ?? true,
      pkceRequired: json['pkce_required'] as bool? ?? true,
      tasklistSelectionRequired:
          json['tasklist_selection_required'] as bool? ?? true,
      callbackPath: json['callback_path'] as String? ??
          '/api/v1/promise-radar/external-task/google-oauth/callback',
      oauthUxReady: json['oauth_ux_ready'] as bool? ?? false,
      tokenExchangeReady: json['token_exchange_ready'] as bool? ?? false,
      productionReady: json['production_ready'] as bool? ?? false,
      missingSetup: (json['missing_setup'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      requiredBackendEnv: (json['required_backend_env'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      verificationSteps: (json['verification_steps'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      steps:
          (json['steps'] as List<dynamic>? ?? []).whereType<String>().toList(),
      tokenHandling: json['token_handling'] as String? ?? '',
      securityNotes: (json['security_notes'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseGoogleTasksOAuthTokenResponse {
  final String provider;
  final bool ready;
  final bool dryRun;
  final String? tokenType;
  final int? expiresIn;
  final String? scope;
  final bool hasAccessToken;
  final bool hasRefreshToken;
  final String? accessToken;
  final String? accessTokenPreview;
  final String? refreshTokenPreview;
  final List<String> missingSetup;
  final String message;
  final List<String> securityNotes;

  const PromiseGoogleTasksOAuthTokenResponse({
    required this.provider,
    required this.ready,
    required this.dryRun,
    this.tokenType,
    this.expiresIn,
    this.scope,
    required this.hasAccessToken,
    required this.hasRefreshToken,
    this.accessToken,
    this.accessTokenPreview,
    this.refreshTokenPreview,
    required this.missingSetup,
    required this.message,
    required this.securityNotes,
  });

  factory PromiseGoogleTasksOAuthTokenResponse.fromJson(
    Map<String, dynamic> json,
  ) {
    return PromiseGoogleTasksOAuthTokenResponse(
      provider: json['provider'] as String? ?? 'google_tasks',
      ready: json['ready'] as bool? ?? false,
      dryRun: json['dry_run'] as bool? ?? true,
      tokenType: json['token_type'] as String?,
      expiresIn: (json['expires_in'] as num?)?.toInt(),
      scope: json['scope'] as String?,
      hasAccessToken: json['has_access_token'] as bool? ?? false,
      hasRefreshToken: json['has_refresh_token'] as bool? ?? false,
      accessToken: json['access_token'] as String?,
      accessTokenPreview: json['access_token_preview'] as String?,
      refreshTokenPreview: json['refresh_token_preview'] as String?,
      missingSetup: (json['missing_setup'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
      message: json['message'] as String? ?? '',
      securityNotes: (json['security_notes'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}

class PromiseCommandCenterAction {
  final String key;
  final String label;
  final String method;
  final String route;
  final bool enabled;
  final bool requiresConfirmation;
  final String? reason;
  final Map<String, dynamic> payload;

  const PromiseCommandCenterAction({
    required this.key,
    required this.label,
    required this.method,
    required this.route,
    required this.enabled,
    required this.requiresConfirmation,
    this.reason,
    required this.payload,
  });

  factory PromiseCommandCenterAction.fromJson(Map<String, dynamic> json) {
    return PromiseCommandCenterAction(
      key: json['key'] as String? ?? '',
      label: json['label'] as String? ?? '',
      method: json['method'] as String? ?? 'GET',
      route: json['route'] as String? ?? '',
      enabled: json['enabled'] as bool? ?? true,
      requiresConfirmation: json['requires_confirmation'] as bool? ?? false,
      reason: json['reason'] as String?,
      payload: (json['payload'] as Map? ?? {}).map(
        (key, value) => MapEntry(key.toString(), value),
      ),
    );
  }
}

class PromiseCommandCenter {
  final String generatedAt;
  final PromiseRadarDashboard dashboard;
  final PromiseAutopilotReviewQueue reviewQueue;
  final PromiseLearningInsight learningInsight;
  final PromiseLearningTelemetryReport learningTelemetry;
  final PromiseDigest digest;
  final PromisePreMeetingBrief preMeetingBrief;
  final PromiseLiveCoachSummary liveCoach;
  final PromiseExternalTaskReconcileResponse externalReconcile;
  final PromiseAccuracyReport accuracyReport;
  final PromiseEvidenceAuditSummary evidenceAudit;
  final PromiseMemoryGraph memoryGraph;
  final PromiseAutopilotShadowSummary shadowMode;
  final PromiseEvidencePermissionSummary evidencePermissions;
  final PromiseEvidenceRoomSummary evidenceRoom;
  final PromiseTeamScorecard teamScorecard;
  final PromiseAutopilotQuarantineSummary autopilotQuarantine;
  final PromiseMeetingRecipePolicy meetingRecipe;
  final PromiseGoogleTasksOAuthGuide googleTasksOAuth;
  final PromiseExtractionRecallReport extractionRecall;
  final List<PromiseCommandCenterAction> actions;
  final List<PromiseCommandCenterFocusItem> focusItems;

  const PromiseCommandCenter({
    required this.generatedAt,
    required this.dashboard,
    required this.reviewQueue,
    required this.learningInsight,
    required this.learningTelemetry,
    required this.digest,
    required this.preMeetingBrief,
    required this.liveCoach,
    required this.externalReconcile,
    required this.accuracyReport,
    required this.evidenceAudit,
    required this.memoryGraph,
    required this.shadowMode,
    required this.evidencePermissions,
    required this.evidenceRoom,
    required this.teamScorecard,
    required this.autopilotQuarantine,
    required this.meetingRecipe,
    required this.googleTasksOAuth,
    required this.extractionRecall,
    required this.actions,
    required this.focusItems,
  });

  factory PromiseCommandCenter.fromJson(Map<String, dynamic> json) {
    return PromiseCommandCenter(
      generatedAt: json['generated_at'] as String? ?? '',
      dashboard: PromiseRadarDashboard.fromJson(
        json['dashboard'] as Map<String, dynamic>? ?? const <String, dynamic>{},
      ),
      reviewQueue: PromiseAutopilotReviewQueue.fromJson(
        json['review_queue'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      learningInsight: PromiseLearningInsight.fromJson(
        json['learning_insight'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      learningTelemetry: PromiseLearningTelemetryReport.fromJson(
        json['learning_telemetry'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      digest: PromiseDigest.fromJson(
        json['digest'] as Map<String, dynamic>? ?? const <String, dynamic>{},
      ),
      preMeetingBrief: PromisePreMeetingBrief.fromJson(
        json['pre_meeting_brief'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      liveCoach: PromiseLiveCoachSummary.fromJson(
        json['live_coach'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      externalReconcile: PromiseExternalTaskReconcileResponse.fromJson(
        json['external_reconcile'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      accuracyReport: PromiseAccuracyReport.fromJson(
        json['accuracy_report'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      extractionRecall: PromiseExtractionRecallReport.fromJson(
        json['extraction_recall'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      evidenceAudit: PromiseEvidenceAuditSummary.fromJson(
        json['evidence_audit'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      memoryGraph: PromiseMemoryGraph.fromJson(
        json['memory_graph'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      shadowMode: PromiseAutopilotShadowSummary.fromJson(
        json['shadow_mode'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      evidencePermissions: PromiseEvidencePermissionSummary.fromJson(
        json['evidence_permissions'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      evidenceRoom: PromiseEvidenceRoomSummary.fromJson(
        json['evidence_room'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      teamScorecard: PromiseTeamScorecard.fromJson(
        json['team_scorecard'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      autopilotQuarantine: PromiseAutopilotQuarantineSummary.fromJson(
        json['autopilot_quarantine'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      meetingRecipe: PromiseMeetingRecipePolicy.fromJson(
        json['meeting_recipe'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      googleTasksOAuth: PromiseGoogleTasksOAuthGuide.fromJson(
        json['google_tasks_oauth'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      actions: (json['actions'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseCommandCenterAction.fromJson)
          .toList(),
      focusItems: (json['focus_items'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PromiseCommandCenterFocusItem.fromJson)
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
