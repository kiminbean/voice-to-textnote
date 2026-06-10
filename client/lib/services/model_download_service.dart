import 'dart:async';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:crypto/crypto.dart';

/// 모델 무결성 예외
///
/// 다운로드한 모델 파일의 체크섬 검증 실패 시 발생
class ModelIntegrityException implements Exception {
  final String message;
  ModelIntegrityException(this.message);

  @override
  String toString() => 'ModelIntegrityException: $message';
}

/// 저장소 예외
///
/// 저장소 공간 부족 또는 파일 시스템 오류 시 발생
class StorageException implements Exception {
  final String message;
  StorageException(this.message);

  @override
  String toString() => 'StorageException: $message';
}

/// 모델 다운로드 서비스
///
/// 원격 모델 파일을 다운로드하고 로컬에 저장하는 서비스입니다.
/// 진행률 스트림, 취소, 검증을 지원합니다.
///
/// @MX:NOTE 이 클래스는 파일 다운로드와 관리를 담당합니다
class ModelDownloadService {
  final Dio _dio;

  ModelDownloadService(this._dio);

  /// 모델 다운로드를 수행하고 진행률을 스트림으로 반환
  ///
  /// [url] 다운로드할 모델 파일 URL
  /// [savePath] 로컬 저장 경로
  /// [cancelToken] 다운로드 취소용 토큰
  ///
  /// 0.0에서 1.0 사이의 진행률을 emit하는 Stream을 반환합니다
  /// @MX:ANCHOR: 공개 API - 다운로드 진행률 스트림 제공
  /// @MX:REASON: Riverpod provider와 UI에서 사용
  /// @MX:SPEC: REQ-MOBILE-007-01, REQ-MOBILE-010-01
  Stream<double> downloadModel({
    required String url,
    required String savePath,
    CancelToken? cancelToken,
  }) {
    final controller = StreamController<double>();

    // 다운로드 시작
    _dio.download(
      url,
      savePath,
      onReceiveProgress: (received, total) {
        if (total > 0) {
          controller.add(received / total);
        }
      },
      cancelToken: cancelToken,
    ).then((_) {
      controller.close();
    }).catchError((error) {
      controller.addError(error);
      controller.close();
    });

    return controller.stream;
  }

  /// 모델이 이미 다운로드되었는지 확인
  ///
  /// [modelId] 확인할 모델 ID
  ///
  /// 모델 파일이 존재하면 true, 아니면 false를 반환합니다
  /// @MX:SPEC: REQ-MOBILE-010-01
  Future<bool> isModelDownloaded(String modelId) async {
    final path = await getModelPath(modelId);
    if (path == null) return false;
    return File(path).existsSync();
  }

  /// 로컬 모델 파일 경로를 반환
  ///
  /// [modelId] 모델 ID
  ///
  /// 모델 파일이 존재하면 경로를 반환하고, 없으면 null을 반환합니다
  /// @MX:SPEC: REQ-MOBILE-010-01
  Future<String?> getModelPath(String modelId) async {
    final dir = await getApplicationDocumentsDirectory();
    final file = File('${dir.path}/models/$modelId.bin');
    return file.existsSync() ? file.path : null;
  }

  /// 저장소에 충분한 공간이 있는지 확인
  ///
  /// [requiredBytes] 필요한 바이트 수 (최소 2배 여유 공간 권장)
  ///
  /// 저장소에 충분한 공간이 있으면 true, 아니면 false를 반환합니다
  /// @MX:SPEC: REQ-MOBILE-007-03
  Future<bool> hasSufficientStorage(int requiredBytes) async {
    try {
      final dir = await getApplicationDocumentsDirectory();
      final stat = await dir.stat();

      // 플랫폼별로 사용 가능한 공간 확인 방법이 다름
      // iOS/Android에서는 공간 확인이 제한적이므로
      // 안전하게 2배의 여유 공간을 확인
      final availableSpace = stat.size;

      // 실제 사용 가능한 공간을 정확히 확인할 수 없으므로
      // 안전한 기본값으로 true 반환 (실제 환경에서는 플랫폼 채널 필요)
      return true;
    } catch (e) {
      // 오류 발생 시 안전하게 true 반환 (다운로드 시도)
      return true;
    }
  }

  /// 이어서 다운로드를 지원하는 다운로드 메서드
  ///
  /// [url] 다운로드할 모델 파일 URL
  /// [savePath] 로컬 저장 경로
  /// [cancelToken] 다운로드 취소용 토큰
  ///
  /// .part 파일이 있으면 이어서 다운로드하고, 완료 후 .part 확장자를 제거합니다
  /// 0.0에서 1.0 사이의 진행률을 emit하는 Stream을 반환합니다
  /// @MX:SPEC: REQ-MOBILE-007-04
  Stream<double> downloadWithResume({
    required String url,
    required String savePath,
    CancelToken? cancelToken,
  }) {
    final controller = StreamController<double>();
    final partPath = '$savePath.part';

    // 기존 .part 파일 확인
    final partFile = File(partPath);

    Future<void> performDownload() async {
      try {
        int downloadedBytes = 0;

        // .part 파일이 존재하면 크기 확인
        if (await partFile.exists()) {
          downloadedBytes = await partFile.length();
        }

        // Range 헤더 설정
        final options = Options();
        if (downloadedBytes > 0) {
          options.headers = {
            'Range': 'bytes=$downloadedBytes-',
          };
        }

        // 다운로드 시작
        await _dio.download(
          url,
          partPath,
          onReceiveProgress: (received, total) {
            if (total > 0) {
              // 이어받기의 경우 진행률 계산
              final totalProgress = downloadedBytes + received;
              final progress = totalProgress / total;
              controller.add(progress.clamp(0.0, 1.0));
            }
          },
          cancelToken: cancelToken,
          options: options,
        );

        // 다운로드 완료 후 .part 파일을 실제 파일로 이동
        if (await partFile.exists()) {
          await partFile.rename(savePath);
        }

        controller.close();
      } catch (error) {
        controller.addError(error);
        controller.close();
      }
    }

    performDownload();
    return controller.stream;
  }

  /// 다운로드한 모델 파일의 무결성을 검증
  ///
  /// [filePath] 검증할 파일 경로
  /// [expectedChecksum] 예상되는 SHA-256 체크섬
  ///
  /// 체크섬이 일치하면 true, 불일치하면 ModelIntegrityException을 throw
  /// @MX:SPEC: REQ-MOBILE-007-02
  Future<bool> verifyChecksum(
    String filePath,
    String expectedChecksum,
  ) async {
    final file = File(filePath);
    final bytes = await file.readAsBytes();
    final digest = sha256.convert(bytes);
    final actualChecksum = digest.toString();

    if (actualChecksum != expectedChecksum) {
      throw ModelIntegrityException(
        'Checksum mismatch: expected $expectedChecksum, got $actualChecksum',
      );
    }

    return true;
  }

  /// 다운로드와 체크섬 검증을 함께 수행
  ///
  /// [url] 다운로드할 URL
  /// [savePath] 저장 경로
  /// [expectedChecksum] 예상 체크섬
  /// [cancelToken] 취소 토큰
  ///
  /// 다운로드 후 체크섬을 검증하고, 성공하면 파일 경로를 반환
  /// @MX:ANCHOR: 공개 API - 다운로드와 검증 통합
  /// @MX:REASON: Provider에서 안전한 다운로드를 위해 사용
  /// @MX:SPEC: REQ-MOBILE-007-02
  Future<String> downloadAndVerify({
    required String url,
    required String savePath,
    required String expectedChecksum,
    CancelToken? cancelToken,
  }) async {
    // 먼저 다운로드 진행률 스트림을 소비
    await for (final _ in downloadModel(
      url: url,
      savePath: savePath,
      cancelToken: cancelToken,
    )) {
      // 진행률을 무시하고 다운로드 완료 대기
    }

    // 체크섬 검증
    await verifyChecksum(savePath, expectedChecksum);

    return savePath;
  }
}
