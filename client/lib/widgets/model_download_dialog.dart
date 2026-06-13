import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/providers/model_download_provider.dart';

/// 모델 다운로드 다이얼로그
///
/// 다운로드 상태에 따라 다른 UI를 표시합니다
/// @MX:SPEC: REQ-MOBILE-010-01, REQ-MOBILE-010-02, REQ-MOBILE-010-03
class ModelDownloadDialog extends ConsumerWidget {
  const ModelDownloadDialog({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(modelDownloadProvider);

    return AlertDialog(
      title: Text(_getTitle(status.state)),
      content: _buildContent(status),
      actions: _buildActions(context, ref, status),
    );
  }

  String _getTitle(DownloadState state) {
    switch (state) {
      case DownloadState.idle:
      case DownloadState.checking:
        return '모델 다운로드';
      case DownloadState.downloading:
        return '다운로드 중...';
      case DownloadState.verifying:
        return '검증 중...';
      case DownloadState.completed:
        return '다운로드 완료';
      case DownloadState.failed:
        return '다운로드 실패';
    }
  }

  Widget _buildContent(DownloadStatus status) {
    switch (status.state) {
      case DownloadState.idle:
      case DownloadState.checking:
        return const Text('모델을 다운로드하시겠습니까?\n약 150MB입니다.');
      case DownloadState.downloading:
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            LinearProgressIndicator(value: status.progress),
            const SizedBox(height: 16),
            Text('${(status.progress * 100).toStringAsFixed(1)}%'),
          ],
        );
      case DownloadState.verifying:
        return const Text('파일 무결성을 검증 중입니다...');
      case DownloadState.completed:
        return const Text('모델 다운로드가 완료되었습니다.');
      case DownloadState.failed:
        return Text(
          '다운로드 실패\n${status.errorMessage ?? "알 수 없는 오류"}',
        );
    }
  }

  List<Widget> _buildActions(
    BuildContext context,
    WidgetRef ref,
    DownloadStatus status,
  ) {
    switch (status.state) {
      case DownloadState.idle:
      case DownloadState.checking:
        return [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('취소'),
          ),
          ElevatedButton(
            onPressed: () {
              // TODO: 다운로드 시작 로직 연결 필요
              final notifier = ref.read(modelDownloadProvider.notifier);
              notifier.startDownload(
                url: 'https://example.com/model.bin',
                savePath: '/path/to/model.bin',
                expectedChecksum: 'abc123',
              );
            },
            child: const Text('다운로드'),
          ),
        ];
      case DownloadState.downloading:
      case DownloadState.verifying:
        return [
          TextButton(
            onPressed: () {
              final notifier = ref.read(modelDownloadProvider.notifier);
              notifier.cancel();
            },
            child: const Text('취소'),
          ),
        ];
      case DownloadState.completed:
        return [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('확인'),
          ),
        ];
      case DownloadState.failed:
        if (status.retryCount < 3) {
          return [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('닫기'),
            ),
            ElevatedButton(
              onPressed: () {
                final notifier = ref.read(modelDownloadProvider.notifier);
                notifier.retry();
              },
              child: const Text('재시도'),
            ),
          ];
        } else {
          return [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('닫기'),
            ),
          ];
        }
    }
  }

  /// 셀룰러 데이터 사용 확인 다이얼로그
  ///
  /// 사용자가 모바일 데이터 사용 시 확인을 받습니다
  /// @MX:SPEC: REQ-MOBILE-010-02
  static Future<bool?> showCellularConfirmation(BuildContext context) {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('모바일 데이터 사용 안내'),
        content: const Text(
          '현재 모바일 데이터를 사용 중입니다.\n약 150MB를 다운로드합니다.\n계속하시겠습니까?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('다운로드'),
          ),
        ],
      ),
    );
  }

  /// 다이얼로그 표시 헬퍼
  ///
  /// [context] BuildContext
  static void show(BuildContext context) {
    showDialog(
      context: context,
      builder: (_) => const ModelDownloadDialog(),
    );
  }
}
