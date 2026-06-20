// 미팅 상태 열거형
enum MeetingStatus {
  recording, // 녹음 중
  scheduled, // 온라인 회의 기록 대기
  processing, // 처리 중 (파이프라인 실행)
  completed, // 완료
  failed, // 실패
}

// 미팅 데이터 모델
class Meeting {
  final String id;
  final String title;
  final DateTime createdAt;
  final MeetingStatus status;
  final Duration? duration;
  // 녹음된 오디오 파일 경로 (파이프라인 시작에 필요)
  final String? audioFilePath;
  // 온라인 회의 링크 (Zoom, Google Meet, Microsoft Teams 등)
  final String? sourceUrl;
  final String? transcriptionTaskId;
  final String? diarizationTaskId;
  final String? minutesTaskId;
  final String? summaryTaskId;
  // STT 정확도 향상용 사용자 사전 ID (Phase 2)
  final String? vocabularyId;

  const Meeting({
    required this.id,
    required this.title,
    required this.createdAt,
    required this.status,
    this.duration,
    this.audioFilePath,
    this.sourceUrl,
    this.transcriptionTaskId,
    this.diarizationTaskId,
    this.minutesTaskId,
    this.summaryTaskId,
    this.vocabularyId,
  });

  // 특정 필드만 변경한 복사본 반환
  Meeting copyWith({
    String? id,
    String? title,
    DateTime? createdAt,
    MeetingStatus? status,
    Duration? duration,
    String? audioFilePath,
    String? sourceUrl,
    String? transcriptionTaskId,
    String? diarizationTaskId,
    String? minutesTaskId,
    String? summaryTaskId,
    String? vocabularyId,
  }) {
    return Meeting(
      id: id ?? this.id,
      title: title ?? this.title,
      createdAt: createdAt ?? this.createdAt,
      status: status ?? this.status,
      duration: duration ?? this.duration,
      audioFilePath: audioFilePath ?? this.audioFilePath,
      sourceUrl: sourceUrl ?? this.sourceUrl,
      transcriptionTaskId: transcriptionTaskId ?? this.transcriptionTaskId,
      diarizationTaskId: diarizationTaskId ?? this.diarizationTaskId,
      minutesTaskId: minutesTaskId ?? this.minutesTaskId,
      summaryTaskId: summaryTaskId ?? this.summaryTaskId,
      vocabularyId: vocabularyId ?? this.vocabularyId,
    );
  }

  // JSON에서 Meeting 객체 생성
  factory Meeting.fromJson(Map<String, dynamic> json) {
    return Meeting(
      id: json['id'] as String,
      title: json['title'] as String,
      createdAt: DateTime.parse(json['createdAt'] as String),
      status: _statusFromString(json['status'] as String),
      duration: json['duration'] != null
          ? Duration(milliseconds: json['duration'] as int)
          : null,
      audioFilePath: json['audioFilePath'] as String?,
      sourceUrl: json['sourceUrl'] as String?,
      transcriptionTaskId: json['transcriptionTaskId'] as String?,
      diarizationTaskId: json['diarizationTaskId'] as String?,
      minutesTaskId: json['minutesTaskId'] as String?,
      summaryTaskId: json['summaryTaskId'] as String?,
      vocabularyId: json['vocabularyId'] as String?,
    );
  }

  // Meeting 객체를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'createdAt': createdAt.toIso8601String(),
      'status': status.name,
      'duration': duration?.inMilliseconds,
      'audioFilePath': audioFilePath,
      'sourceUrl': sourceUrl,
      'transcriptionTaskId': transcriptionTaskId,
      'diarizationTaskId': diarizationTaskId,
      'minutesTaskId': minutesTaskId,
      'summaryTaskId': summaryTaskId,
      'vocabularyId': vocabularyId,
    };
  }

  // 문자열에서 MeetingStatus 변환
  static MeetingStatus _statusFromString(String value) {
    switch (value) {
      case 'recording':
        return MeetingStatus.recording;
      case 'scheduled':
        return MeetingStatus.scheduled;
      case 'processing':
        return MeetingStatus.processing;
      case 'completed':
        return MeetingStatus.completed;
      case 'failed':
        return MeetingStatus.failed;
      default:
        return MeetingStatus.failed;
    }
  }
}
