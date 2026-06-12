import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/model_download_service.dart';

/// 다운로드 상태 열거형
///
/// 모델 다운로드의 현재 상태를 나타냅니다
/// @MX:SPEC: REQ-MOBILE-010
enum DownloadState {
  /// 대기 상태
  idle,

  /// 저장소 공간 확인 중
  checking,

  /// 다운로드 중
  downloading,

  /// 체크섬 검증 중
  verifying,

  /// 완료
  completed,

  /// 실패
  failed,
}

/// 다운로드 상태 모델
///
/// 다운로드 진행 상황과 관련 정보를 포함합니다
/// @MX:SPEC: REQ-MOBILE-010
class DownloadStatus {
  /// 현재 상태
  final DownloadState state;

  /// 진행률 (0.0 ~ 1.0)
  final double progress;

  /// 에러 메시지 (실패 시)
  final String? errorMessage;

  /// 재시도 횟수
  final int retryCount;

  /// WiFi 사용 여부
  final bool isWifi;

  const DownloadStatus({
    required this.state,
    this.progress = 0.0,
    this.errorMessage,
    this.retryCount = 0,
    this.isWifi = true,
  });

  /// 초기 상태 생성
  factory DownloadStatus.initial() {
    return const DownloadStatus(
      state: DownloadState.idle,
      progress: 0.0,
      retryCount: 0,
      isWifi: true,
    );
  }

  /// 상태 복사
  DownloadStatus copyWith({
    DownloadState? state,
    double? progress,
    String? errorMessage,
    int? retryCount,
    bool? isWifi,
  }) {
    return DownloadStatus(
      state: state ?? this.state,
      progress: progress ?? this.progress,
      errorMessage: errorMessage ?? this.errorMessage,
      retryCount: retryCount ?? this.retryCount,
      isWifi: isWifi ?? this.isWifi,
    );
  }
}

/// 다운로드 관리 Notifier
///
/// 모델 다운로드를 관리하고 상태를 업데이트합니다
/// @MX:SPEC: REQ-MOBILE-010
class ModelDownloadNotifier extends Notifier<DownloadStatus> {
  CancelToken? _cancelToken;
  _DownloadRequest? _lastRequest;
  static const int maxRetries = 3;

  @override
  DownloadStatus build() {
    return DownloadStatus.initial();
  }

  /// 다운로드 시작
  ///
  /// [url] 다운로드할 모델 파일 URL
  /// [savePath] 로컬 저장 경로
  /// [expectedChecksum] 예상 체크섬
  /// [isWifi] WiFi 사용 여부
  Future<void> startDownload({
    required String url,
    required String savePath,
    required String expectedChecksum,
    int? requiredBytes,
    bool isWifi = true,
  }) async {
    _lastRequest = _DownloadRequest(
      url: url,
      savePath: savePath,
      expectedChecksum: expectedChecksum,
      requiredBytes: requiredBytes,
      isWifi: isWifi,
    );
    _cancelToken = CancelToken();

    // checking 상태로 변경
    state = state.copyWith(
      state: DownloadState.checking,
      isWifi: isWifi,
      errorMessage: null,
    );

    try {
      final service = ref.read(modelDownloadServiceProvider);
      if (requiredBytes != null &&
          !await service.hasSufficientStorage(requiredBytes)) {
        throw StorageException('저장 공간이 부족합니다');
      }

      // downloading 상태로 변경
      state = state.copyWith(state: DownloadState.downloading);

      await for (final progress in service.downloadWithResume(
        url: url,
        savePath: savePath,
        cancelToken: _cancelToken,
      )) {
        state = state.copyWith(
          state: DownloadState.downloading,
          progress: progress,
        );
      }

      // verifying 상태로 변경
      state = state.copyWith(
        state: DownloadState.verifying,
        progress: 1.0,
      );

      await service.verifyChecksum(savePath, expectedChecksum);

      // completed 상태로 변경
      state = DownloadStatus(
        state: DownloadState.completed,
        progress: 1.0,
        retryCount: state.retryCount,
        isWifi: state.isWifi,
      );
    } catch (e) {
      // failed 상태로 변경
      state = DownloadStatus(
        state: DownloadState.failed,
        errorMessage: e.toString(),
        retryCount: state.retryCount,
      );
    }
  }

  /// 재시도
  Future<void> retry() async {
    final request = _lastRequest;
    if (request == null || state.retryCount >= maxRetries) {
      return;
    }

    final retryCount = state.retryCount + 1;
    state = state.copyWith(retryCount: retryCount);

    await startDownload(
      url: request.url,
      savePath: request.savePath,
      expectedChecksum: request.expectedChecksum,
      requiredBytes: request.requiredBytes,
      isWifi: request.isWifi,
    );
    state = state.copyWith(retryCount: retryCount);
  }

  /// 취소
  void cancel() {
    _cancelToken?.cancel('Download cancelled by user');
    state = DownloadStatus.initial();
  }

  /// 초기화
  void reset() {
    state = DownloadStatus.initial();
  }
}

class _DownloadRequest {
  final String url;
  final String savePath;
  final String expectedChecksum;
  final int? requiredBytes;
  final bool isWifi;

  const _DownloadRequest({
    required this.url,
    required this.savePath,
    required this.expectedChecksum,
    required this.requiredBytes,
    required this.isWifi,
  });
}

final modelDownloadServiceProvider = Provider<ModelDownloadService>((ref) {
  return ModelDownloadService(Dio());
});

/// 다운로드 상태 Provider
///
/// 앱 전체에서 다운로드 상태를 관리합니다
/// @MX:ANCHOR: 공개 API - 다운로드 상태 관리
/// @MX:REASON: Riverpod provider 패턴, UI에서 상태 구독
/// @MX:SPEC: REQ-MOBILE-010
final modelDownloadProvider =
    NotifierProvider<ModelDownloadNotifier, DownloadStatus>(
  ModelDownloadNotifier.new,
);
