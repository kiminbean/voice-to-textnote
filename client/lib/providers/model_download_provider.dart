// SPEC-MOBILE-002: 모델 다운로드 상태 관리 프로바이더
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/model_manager.dart';

final modelDownloadProvider =
    StateNotifierProvider<ModelDownloadNotifier, SttModelStatus>((ref) {
  final manager = ref.watch(modelManagerProvider);
  return ModelDownloadNotifier(manager);
});

class ModelDownloadNotifier extends StateNotifier<SttModelStatus> {
  final SttModelManager _manager;
  CancelToken? _cancelToken;

  ModelDownloadNotifier(this._manager) : super(const SttModelStatus.initial()) {
    _checkInitialStatus();
  }

  Future<void> _checkInitialStatus() async {
    final ready = await _manager.isModelReady();
    if (ready) {
      state = const SttModelStatus(
        state: ModelDownloadState.ready,
        progress: 1.0,
      );
    }
  }

  /// 모델 다운로드 시작 (Dio 진행률 추적 + 크기 검증)
  Future<void> download() async {
    if (state.state == ModelDownloadState.downloading) return;

    state = const SttModelStatus(
      state: ModelDownloadState.downloading,
      progress: 0.0,
    );

    final model = _manager.defaultModel;
    final dio = Dio();
    _cancelToken = CancelToken();

    try {
      final expectedPath = await _manager.getExpectedModelPath();
      final tempPath = '$expectedPath.tmp';
      final tempFile = File(tempPath);

      await dio.download(
        model.downloadUrl,
        tempPath,
        cancelToken: _cancelToken,
        onReceiveProgress: (received, total) {
          if (total > 0 && mounted) {
            state = state.copyWith(
              progress: received / total,
            );
          }
        },
        options: Options(
          receiveTimeout: const Duration(minutes: 10),
        ),
      );

      // 다운로드 완료 → 크기 검증
      state = state.copyWith(
        state: ModelDownloadState.verifying,
        progress: 1.0,
      );

      final actualSize = tempFile.lengthSync();
      if (actualSize != model.sizeBytes) {
        await tempFile.delete();
        state = SttModelStatus(
          state: ModelDownloadState.error,
          errorMessage: '모델 크기 불일치 (${actualSize}B != ${model.sizeBytes}B)',
        );
        return;
      }

      // 검증 통과 → 최종 위치로 이동
      final finalFile = await _manager.getModelFile();
      if (finalFile.existsSync()) {
        await finalFile.delete();
      }
      await tempFile.rename(finalFile.path);

      await _manager.markModelReady(finalFile.path);

      state = const SttModelStatus(
        state: ModelDownloadState.ready,
        progress: 1.0,
      );
    } on DioException catch (e) {
      if (CancelToken.isCancel(e)) {
        state = const SttModelStatus.initial();
        return;
      }
      state = SttModelStatus(
        state: ModelDownloadState.error,
        errorMessage: '다운로드 실패: ${e.message}',
      );
    } catch (e) {
      state = SttModelStatus(
        state: ModelDownloadState.error,
        errorMessage: '다운로드 실패: $e',
      );
    } finally {
      dio.close();
      _cancelToken = null;
    }
  }

  /// 다운로드 취소
  void cancelDownload() {
    _cancelToken?.cancel('사용자가 다운로드를 취소했습니다');
    state = const SttModelStatus.initial();
  }

  /// 모델 삭제
  Future<void> deleteModel() async {
    await _manager.deleteModel();
    state = const SttModelStatus.initial();
  }

  @override
  void dispose() {
    _cancelToken?.cancel('Provider disposed');
    super.dispose();
  }
}
