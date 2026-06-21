import 'package:voice_to_textnote/models/study_pack.dart';

class SalesContactIdentity {
  final String? name;
  final String? company;
  final String? role;
  final String? email;
  final String? phone;

  const SalesContactIdentity({
    this.name,
    this.company,
    this.role,
    this.email,
    this.phone,
  });

  factory SalesContactIdentity.fromJson(Map<String, dynamic> json) =>
      SalesContactIdentity(
        name: json['name'] as String?,
        company: json['company'] as String?,
        role: json['role'] as String?,
        email: json['email'] as String?,
        phone: json['phone'] as String?,
      );
}

class SalesContactDeal {
  final String stage;
  final String? valueHint;
  final String urgency;

  const SalesContactDeal({
    this.stage = 'unknown',
    this.valueHint,
    this.urgency = 'unknown',
  });

  factory SalesContactDeal.fromJson(Map<String, dynamic> json) =>
      SalesContactDeal(
        stage: json['stage'] as String? ?? 'unknown',
        valueHint: json['value_hint'] as String?,
        urgency: json['urgency'] as String? ?? 'unknown',
      );
}

class SalesNextStep {
  final String task;
  final String? owner;
  final String? due;

  const SalesNextStep({
    required this.task,
    this.owner,
    this.due,
  });

  factory SalesNextStep.fromJson(Map<String, dynamic> json) => SalesNextStep(
        task: json['task'] as String? ?? '',
        owner: json['owner'] as String?,
        due: json['due'] as String?,
      );
}

class SalesContactBrief {
  final String taskId;
  final SalesContactIdentity contact;
  final SalesContactDeal deal;
  final List<String> customerNeeds;
  final List<String> painPoints;
  final List<String> objections;
  final List<SalesNextStep> nextSteps;
  final String followUpMessage;
  final List<StudySourceRef> sourceRefs;
  final String createdAt;

  const SalesContactBrief({
    required this.taskId,
    required this.contact,
    required this.deal,
    required this.customerNeeds,
    required this.painPoints,
    required this.objections,
    required this.nextSteps,
    required this.followUpMessage,
    required this.sourceRefs,
    required this.createdAt,
  });

  factory SalesContactBrief.fromJson(Map<String, dynamic> json) =>
      SalesContactBrief(
        taskId: json['task_id'] as String? ?? '',
        contact: SalesContactIdentity.fromJson(
          json['contact'] as Map<String, dynamic>? ?? const {},
        ),
        deal: SalesContactDeal.fromJson(
          json['deal'] as Map<String, dynamic>? ?? const {},
        ),
        customerNeeds: _parseStringList(json['customer_needs']),
        painPoints: _parseStringList(json['pain_points']),
        objections: _parseStringList(json['objections']),
        nextSteps: (json['next_steps'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(SalesNextStep.fromJson)
            .toList(),
        followUpMessage: json['follow_up_message'] as String? ?? '',
        sourceRefs: (json['source_refs'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(StudySourceRef.fromJson)
            .toList(),
        createdAt: json['created_at'] as String? ?? '',
      );
}

class SalesContactListItem {
  final String artifactTaskId;
  final String sourceTaskId;
  final SalesContactIdentity contact;
  final SalesContactDeal deal;
  final List<String> customerNeeds;
  final List<String> painPoints;
  final List<SalesNextStep> nextSteps;
  final String followUpMessage;
  final String crmStatus;
  final String crmNote;
  final String? crmUpdatedAt;
  final String createdAt;
  final String? completedAt;

  const SalesContactListItem({
    required this.artifactTaskId,
    required this.sourceTaskId,
    required this.contact,
    required this.deal,
    required this.customerNeeds,
    required this.painPoints,
    required this.nextSteps,
    required this.followUpMessage,
    this.crmStatus = 'open',
    this.crmNote = '',
    this.crmUpdatedAt,
    required this.createdAt,
    this.completedAt,
  });

  factory SalesContactListItem.fromJson(Map<String, dynamic> json) =>
      SalesContactListItem(
        artifactTaskId: json['artifact_task_id'] as String? ?? '',
        sourceTaskId: json['source_task_id'] as String? ?? '',
        contact: SalesContactIdentity.fromJson(
          json['contact'] as Map<String, dynamic>? ?? const {},
        ),
        deal: SalesContactDeal.fromJson(
          json['deal'] as Map<String, dynamic>? ?? const {},
        ),
        customerNeeds: _parseStringList(json['customer_needs']),
        painPoints: _parseStringList(json['pain_points']),
        nextSteps: (json['next_steps'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(SalesNextStep.fromJson)
            .toList(),
        followUpMessage: json['follow_up_message'] as String? ?? '',
        crmStatus: json['crm_status'] as String? ?? 'open',
        crmNote: json['crm_note'] as String? ?? '',
        crmUpdatedAt: json['crm_updated_at'] as String?,
        createdAt: json['created_at'] as String? ?? '',
        completedAt: json['completed_at'] as String?,
      );
}

class SalesContactListResponse {
  final List<SalesContactListItem> items;
  final int total;
  final int page;
  final int pageSize;

  const SalesContactListResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
  });

  factory SalesContactListResponse.fromJson(Map<String, dynamic> json) =>
      SalesContactListResponse(
        items: (json['items'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(SalesContactListItem.fromJson)
            .toList(),
        total: json['total'] as int? ?? 0,
        page: json['page'] as int? ?? 1,
        pageSize: json['page_size'] as int? ?? 20,
      );
}

List<String> _parseStringList(dynamic value) {
  if (value is! List) return [];
  return value
      .map((item) => item.toString())
      .where((item) => item.isNotEmpty)
      .toList();
}
