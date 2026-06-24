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
  final String? voiceprintEnrollmentStatus;
  final int? voiceprintSampleCount;
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
    this.voiceprintEnrollmentStatus,
    this.voiceprintSampleCount,
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
      voiceprintEnrollmentStatus:
          json['voiceprint_enrollment_status'] as String?,
      voiceprintSampleCount: json['voiceprint_sample_count'] as int?,
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
  final String? enrollmentTaskId;

  const SpeakerProfileCreate({
    required this.speakerLabel,
    required this.displayName,
    this.role,
    this.note,
    this.taskId,
    this.enrollmentTaskId,
  });

  Map<String, dynamic> toJson() => {
        'speaker_label': speakerLabel,
        'display_name': displayName,
        if (role != null) 'role': role,
        if (note != null) 'note': note,
        if (taskId != null) 'task_id': taskId,
        if (enrollmentTaskId != null) 'enrollment_task_id': enrollmentTaskId,
      };
}

/// 화자 프로필 수정 요청 (모든 필드 선택)
class SpeakerProfileUpdate {
  final String? displayName;
  final String? role;
  final String? note;
  final String? enrollmentTaskId;
  final String? enrollmentSpeakerLabel;

  const SpeakerProfileUpdate({
    this.displayName,
    this.role,
    this.note,
    this.enrollmentTaskId,
    this.enrollmentSpeakerLabel,
  });

  Map<String, dynamic> toJson() => {
        if (displayName != null) 'display_name': displayName,
        if (role != null) 'role': role,
        if (note != null) 'note': note,
        if (enrollmentTaskId != null) 'enrollment_task_id': enrollmentTaskId,
        if (enrollmentSpeakerLabel != null)
          'enrollment_speaker_label': enrollmentSpeakerLabel,
      };
}

class SpeakerVoiceprintBackfillResult {
  final int scannedProfiles;
  final int enrolledProfiles;
  final int skippedProfiles;
  final List<String> missingVoiceprints;

  const SpeakerVoiceprintBackfillResult({
    required this.scannedProfiles,
    required this.enrolledProfiles,
    required this.skippedProfiles,
    this.missingVoiceprints = const [],
  });

  factory SpeakerVoiceprintBackfillResult.fromJson(Map<String, dynamic> json) {
    return SpeakerVoiceprintBackfillResult(
      scannedProfiles: json['scanned_profiles'] as int? ?? 0,
      enrolledProfiles: json['enrolled_profiles'] as int? ?? 0,
      skippedProfiles: json['skipped_profiles'] as int? ?? 0,
      missingVoiceprints: (json['missing_voiceprints'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
    );
  }
}
