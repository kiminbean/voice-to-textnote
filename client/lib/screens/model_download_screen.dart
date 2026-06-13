// SPEC-MOBILE-002: 오프라인 STT 모델 다운로드 화면
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/model_download_provider.dart';
import 'package:voice_to_textnote/services/model_manager.dart';

class ModelDownloadScreen extends ConsumerWidget {
  const ModelDownloadScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(modelDownloadProvider);
    final notifier = ref.read(modelDownloadProvider.notifier);
    final model = ref.read(modelManagerProvider).defaultModel;

    return Scaffold(
      appBar: AppBar(
        title: const Text('오프라인 STT 모델'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(Icons.cloud_download, size: 64),
            const SizedBox(height: 16),
            Text(
              model.displayName,
              style: Theme.of(context).textTheme.headlineSmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              '${(model.sizeBytes / 1024 / 1024).toStringAsFixed(1)} MB',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.grey[600],
                  ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            _buildContent(context, status, notifier),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(
    BuildContext context,
    SttModelStatus status,
    ModelDownloadNotifier notifier,
  ) {
    switch (status.state) {
      case ModelDownloadState.notDownloaded:
        return ElevatedButton.icon(
          onPressed: notifier.download,
          icon: const Icon(Icons.download),
          label: const Text('모델 다운로드'),
        );

      case ModelDownloadState.downloading:
        return Column(
          children: [
            LinearProgressIndicator(value: status.progress),
            const SizedBox(height: 8),
            Text('${(status.progress * 100).toStringAsFixed(0)}%'),
            const SizedBox(height: 16),
            TextButton(
              onPressed: notifier.cancelDownload,
              child: const Text('취소'),
            ),
          ],
        );

      case ModelDownloadState.verifying:
        return const Column(
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('모델 검증 중...'),
          ],
        );

      case ModelDownloadState.ready:
        return Column(
          children: [
            const Icon(Icons.check_circle, color: Colors.green, size: 48),
            const SizedBox(height: 16),
            const Text('모델이 설치되었습니다'),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: notifier.deleteModel,
              icon: const Icon(Icons.delete_outline),
              label: const Text('모델 삭제'),
            ),
          ],
        );

      case ModelDownloadState.error:
        return Column(
          children: [
            const Icon(Icons.error, color: Colors.red, size: 48),
            const SizedBox(height: 16),
            Text(
              status.errorMessage ?? '알 수 없는 오류',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.red[700]),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: notifier.download,
              icon: const Icon(Icons.refresh),
              label: const Text('재시도'),
            ),
          ],
        );
    }
  }
}
