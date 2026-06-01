// 화자 프로필 모델 — SPEC-SPEAKER-001
// 전역(task_id == null) + 회의별 오버라이드(task_id 지정) 지원

class SpeakerProfile {
  final String id;
  final String userId;
  final String speakerLabel;
  final String displayName;
  final String? role;
  final String? note;
  final String? taskId;
  final DateTime createdAt;
  final DateTime updatedAt;

  const SpeakerProfile({
    required this.id,
    required this.userId,
    required this.speakerLabel,
    required this.displayName,
    this.role,
    this.note,
    this.taskId,
    required this.createdAt,
    required this.updatedAt,
  });

  factory SpeakerProfile.fromJson(Map<String, dynamic> json) {
    return SpeakerProfile(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      speakerLabel: json['speaker_label'] as String,
      displayName: json['display_name'] as String,
      role: json['role'] as String?,
      note: json['note'] as String?,
      taskId: json['task_id'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}

/// 화자 프로필 생성 요청
class SpeakerProfileCreate {
  final String speakerLabel;
  final String displayName;
  final String? role;
  final String? note;
  final String? taskId;

  const SpeakerProfileCreate({
    required this.speakerLabel,
    required this.displayName,
    this.role,
    this.note,
    this.taskId,
  });

  Map<String, dynamic> toJson() => {
        'speaker_label': speakerLabel,
        'display_name': displayName,
        if (role != null) 'role': role,
        if (note != null) 'note': note,
        if (taskId != null) 'task_id': taskId,
      };
}

/// 화자 프로필 수정 요청 (모든 필드 선택)
class SpeakerProfileUpdate {
  final String? displayName;
  final String? role;
  final String? note;

  const SpeakerProfileUpdate({this.displayName, this.role, this.note});

  Map<String, dynamic> toJson() => {
        if (displayName != null) 'display_name': displayName,
        if (role != null) 'role': role,
        if (note != null) 'note': note,
      };
}
