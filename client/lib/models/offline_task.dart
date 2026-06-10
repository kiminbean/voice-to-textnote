// 오프라인 STT 결과 재처리 추적 모델
// @MX:NOTE: 네트워크 복구 시 백엔드 재처리 대상을 관리

/// 오프라인 작업 상태
enum OfflineTaskStatus {
  /// 재처리 대기 중
  pending,

  /// 백엔드 재처리 중
  reprocessing,

  /// 재처리 완료 (온라인 결과로 교체됨)
  completed,

  /// 재처리 실패
  failed,
}

/// 오프라인 STT 결과 재처리 작업
class OfflineTask {
  /// 고유 ID
  final String id;

  /// 오디오 파일 경로
  final String audioPath;

  /// 오프라인 전사 결과 파일 경로
  final String offlineTranscriptionPath;

  /// 백엔드 온라인 전사 작업 ID (재처리 시작 시 할당)
  final String? onlineTranscriptionTaskId;

  /// 현재 상태
  final OfflineTaskStatus status;

  /// 생성 시각
  final DateTime createdAt;

  /// 재처리 완료 시각
  final DateTime? reprocessedAt;

  /// 에러 메시지 (실패 시)
  final String? errorMessage;

  const OfflineTask({
    required this.id,
    required this.audioPath,
    required this.offlineTranscriptionPath,
    this.onlineTranscriptionTaskId,
    required this.status,
    required this.createdAt,
    this.reprocessedAt,
    this.errorMessage,
  });

  /// 지정된 필드만 업데이트한 복사본 반환
  OfflineTask copyWith({
    String? id,
    String? audioPath,
    String? offlineTranscriptionPath,
    String? onlineTranscriptionTaskId,
    OfflineTaskStatus? status,
    DateTime? createdAt,
    DateTime? reprocessedAt,
    String? errorMessage,
  }) {
    return OfflineTask(
      id: id ?? this.id,
      audioPath: audioPath ?? this.audioPath,
      offlineTranscriptionPath:
          offlineTranscriptionPath ?? this.offlineTranscriptionPath,
      onlineTranscriptionTaskId:
          onlineTranscriptionTaskId ?? this.onlineTranscriptionTaskId,
      status: status ?? this.status,
      createdAt: createdAt ?? this.createdAt,
      reprocessedAt: reprocessedAt ?? this.reprocessedAt,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }

  /// JSON에서 객체 생성
  factory OfflineTask.fromJson(Map<String, dynamic> json) {
    return OfflineTask(
      id: json['id'] as String,
      audioPath: json['audio_path'] as String,
      offlineTranscriptionPath: json['offline_transcription_path'] as String,
      onlineTranscriptionTaskId:
          json['online_transcription_task_id'] as String?,
      status: _parseStatus(json['status'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      reprocessedAt: json['reprocessed_at'] != null
          ? DateTime.parse(json['reprocessed_at'] as String)
          : null,
      errorMessage: json['error_message'] as String?,
    );
  }

  /// 객체를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'audio_path': audioPath,
      'offline_transcription_path': offlineTranscriptionPath,
      'online_transcription_task_id': onlineTranscriptionTaskId,
      'status': _statusToString(status),
      'created_at': createdAt.toUtc().toIso8601String(),
      'reprocessed_at': reprocessedAt?.toUtc().toIso8601String(),
      'error_message': errorMessage,
    };
  }

  /// 상태 문자열 파싱
  static OfflineTaskStatus _parseStatus(String status) {
    switch (status) {
      case 'pending':
        return OfflineTaskStatus.pending;
      case 'reprocessing':
        return OfflineTaskStatus.reprocessing;
      case 'completed':
        return OfflineTaskStatus.completed;
      case 'failed':
        return OfflineTaskStatus.failed;
      default:
        throw ArgumentError('Invalid OfflineTaskStatus: $status');
    }
  }

  /// 상태를 문자열로 변환
  static String _statusToString(OfflineTaskStatus status) {
    switch (status) {
      case OfflineTaskStatus.pending:
        return 'pending';
      case OfflineTaskStatus.reprocessing:
        return 'reprocessing';
      case OfflineTaskStatus.completed:
        return 'completed';
      case OfflineTaskStatus.failed:
        return 'failed';
    }
  }
}
