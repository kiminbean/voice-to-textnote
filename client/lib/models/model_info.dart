// 모델 다운로드 상태 열거형
enum ModelStatusType {
  notDownloaded,
  downloading,
  downloaded,
  verified,
  error,
}

// 모델 다운로드 상태를 나타내는 클래스
// @MX:ANCHOR: 오프라인 STT 모델 상태 관리 - ModelDownloadService, SettingsScreen 참조
// @MX:REASON: fan_in >= 3 (다운로드 서비스, 설정 화면, 홈 화면에서 사용)
class ModelStatus {
  final ModelStatusType type;
  final double? progress; // downloading 상태일 때 0.0 ~ 1.0
  final String? errorMessage; // error 상태일 때 오류 메시지

  const ModelStatus({
    required this.type,
    this.progress,
    this.errorMessage,
  });

  // 다운로드 안 됨
  const ModelStatus.notDownloaded()
      : type = ModelStatusType.notDownloaded,
        progress = null,
        errorMessage = null;

  // 다운로드 중 (progress: 0.0 ~ 1.0)
  const ModelStatus.downloading(this.progress)
      : type = ModelStatusType.downloading,
        errorMessage = null;

  // 다운로드 완료
  const ModelStatus.downloaded()
      : type = ModelStatusType.downloaded,
        progress = null,
        errorMessage = null;

  // 검증 완료 (사용 가능)
  const ModelStatus.verified()
      : type = ModelStatusType.verified,
        progress = null,
        errorMessage = null;

  // 오류 발생
  const ModelStatus.error(this.errorMessage)
      : type = ModelStatusType.error,
        progress = null;

  @override
  String toString() {
    switch (type) {
      case ModelStatusType.notDownloaded:
        return 'ModelStatus.notDownloaded';
      case ModelStatusType.downloading:
        return 'ModelStatus.downloading(progress: $progress)';
      case ModelStatusType.downloaded:
        return 'ModelStatus.downloaded';
      case ModelStatusType.verified:
        return 'ModelStatus.verified';
      case ModelStatusType.error:
        return 'ModelStatus.error(message: $errorMessage)';
    }
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is ModelStatus &&
        other.type == type &&
        other.progress == progress &&
        other.errorMessage == errorMessage;
  }

  @override
  int get hashCode => type.hashCode ^ progress.hashCode ^ errorMessage.hashCode;
}

// @MX:ANCHOR: 오프라인 STT 모델 정보 - ModelDownloadService, SettingsScreen, HomeScreen 참조
// @MX:REASON: fan_in >= 3 (다운로드 서비스, 설정 화면, 홈 화면에서 사용)
class ModelInfo {
  final String modelId; // 예: "whisper-base"
  final String version; // 예: "1.0.0"
  final int sizeBytes; // 예상 파일 크기
  final String expectedChecksum; // SHA-256 해시
  final ModelStatus status;
  final String? localPath; // 다운로드된 로컬 경로
  final DateTime? downloadedAt; // 다운로드 완료 시간
  final String? downloadUrl; // 다운로드 URL

  const ModelInfo({
    required this.modelId,
    required this.version,
    required this.sizeBytes,
    required this.expectedChecksum,
    required this.status,
    this.localPath,
    this.downloadedAt,
    this.downloadUrl,
  });

  // 특정 필드만 변경한 복사본 반환
  // nullable 필드를 null로 명시적 초기화하려면 clear* 플래그를 true로 설정
  ModelInfo copyWith({
    String? modelId,
    String? version,
    int? sizeBytes,
    String? expectedChecksum,
    ModelStatus? status,
    String? localPath,
    bool clearLocalPath = false,
    DateTime? downloadedAt,
    bool clearDownloadedAt = false,
    String? downloadUrl,
    bool clearDownloadUrl = false,
  }) {
    return ModelInfo(
      modelId: modelId ?? this.modelId,
      version: version ?? this.version,
      sizeBytes: sizeBytes ?? this.sizeBytes,
      expectedChecksum: expectedChecksum ?? this.expectedChecksum,
      status: status ?? this.status,
      localPath: clearLocalPath ? null : (localPath ?? this.localPath),
      downloadedAt:
          clearDownloadedAt ? null : (downloadedAt ?? this.downloadedAt),
      downloadUrl: clearDownloadUrl ? null : (downloadUrl ?? this.downloadUrl),
    );
  }

  // JSON에서 ModelInfo 객체 생성
  factory ModelInfo.fromJson(Map<String, dynamic> json) {
    final statusStr = json['status'] as String;

    ModelStatus parseStatus() {
      switch (statusStr) {
        case 'notDownloaded':
          return const ModelStatus.notDownloaded();
        case 'downloading':
          return ModelStatus.downloading(json['progress'] as double? ?? 0.0);
        case 'downloaded':
          return const ModelStatus.downloaded();
        case 'verified':
          return const ModelStatus.verified();
        case 'error':
          return ModelStatus.error(
              json['errorMessage'] as String? ?? 'Unknown error');
        default:
          return const ModelStatus.notDownloaded();
      }
    }

    return ModelInfo(
      modelId: json['modelId'] as String,
      version: json['version'] as String,
      sizeBytes: json['sizeBytes'] as int,
      expectedChecksum: json['expectedChecksum'] as String,
      status: parseStatus(),
      localPath: json['localPath'] as String?,
      downloadedAt: json['downloadedAt'] != null
          ? DateTime.parse(json['downloadedAt'] as String)
          : null,
      downloadUrl: json['downloadUrl'] as String?,
    );
  }

  // ModelInfo 객체를 JSON으로 변환
  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{
      'modelId': modelId,
      'version': version,
      'sizeBytes': sizeBytes,
      'expectedChecksum': expectedChecksum,
      'status': switch (status.type) {
        ModelStatusType.notDownloaded => 'notDownloaded',
        ModelStatusType.downloading => 'downloading',
        ModelStatusType.downloaded => 'downloaded',
        ModelStatusType.verified => 'verified',
        ModelStatusType.error => 'error',
      },
    };

    // 상태별 추가 필드
    if (status.type == ModelStatusType.downloading) {
      json['progress'] = status.progress;
    } else if (status.type == ModelStatusType.error) {
      json['errorMessage'] = status.errorMessage;
    }

    // 옵셔널 필드
    if (localPath != null) {
      json['localPath'] = localPath;
    }
    if (downloadedAt != null) {
      // UTC인 경우 'Z' 접미사 추가
      final isoString = downloadedAt!.toIso8601String();
      json['downloadedAt'] =
          isoString.endsWith('Z') ? isoString : '${isoString}Z';
    }
    if (downloadUrl != null) {
      json['downloadUrl'] = downloadUrl;
    }

    return json;
  }

  @override
  String toString() {
    return 'ModelInfo(modelId: $modelId, version: $version, status: $status)';
  }
}
