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
    bool isWifi = true,
  }) async {
    // checking 상태로 변경
    state = state.copyWith(
      state: DownloadState.checking,
      isWifi: isWifi,
    );

    try {
      // 저장소 공간 확인 (TODO: 실제 구현 필요)
      // await hasSufficientStorage();

      // downloading 상태로 변경
      state = state.copyWith(state: DownloadState.downloading);

      // TODO: 실제 다운로드 로직 구현 필요
      // 여기서는 시뮬레이션만 수행
      await Future.delayed(const Duration(milliseconds: 100));

      // verifying 상태로 변경
      state = state.copyWith(
        state: DownloadState.verifying,
        progress: 1.0,
      );

      // TODO: 체크섬 검증 구현 필요
      await Future.delayed(const Duration(milliseconds: 50));

      // completed 상태로 변경
      state = const DownloadStatus(state: DownloadState.completed);
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
    if (state.retryCount >= maxRetries) {
      return;
    }

    state = state.copyWith(retryCount: state.retryCount + 1);

    // TODO: 이전 다운로드 파라미터로 재시도
    // 현재는 단순 시뮬레이션
    await startDownload(
      url: 'https://example.com/model.bin',
      savePath: '/tmp/model.bin',
      expectedChecksum: 'abc123',
    );
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
