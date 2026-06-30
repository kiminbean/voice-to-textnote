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
      followUpQuestions: (json['follow_up_questions'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList(),
    );
  }
}
