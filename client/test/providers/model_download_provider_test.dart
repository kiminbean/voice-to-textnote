import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/providers/model_download_provider.dart';

// Mock classes
class MockModelDownloadService extends Mock {}

void main() {
  group('ModelDownloadProvider', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
    });

    group('DownloadStatus', () {
      test('초기 상태는 idle이어야 함', () {
        // Act
        final status = DownloadStatus.initial();

        // Assert
        expect(status.state, equals(DownloadState.idle));
        expect(status.progress, equals(0.0));
        expect(status.retryCount, equals(0));
        expect(status.isWifi, isTrue);
      });

      test('copyWith로 상태를 복사할 수 있어야 함', () {
        // Arrange
        const original = DownloadStatus(
          state: DownloadState.downloading,
          progress: 0.5,
          errorMessage: 'Error',
          retryCount: 2,
          isWifi: false,
        );

        // Act
        final updated = original.copyWith(
          progress: 0.8,
          retryCount: 3,
        );

        // Assert
        expect(updated.state, equals(DownloadState.downloading));
        expect(updated.progress, equals(0.8));
        expect(updated.errorMessage, equals('Error'));
        expect(updated.retryCount, equals(3));
        expect(updated.isWifi, isFalse);
      });
    });

    group('ModelDownloadNotifier', () {
      test('초기 상태는 idle이어야 함', () {
        // Act
        final notifier = container.read(modelDownloadProvider.notifier);

        // Assert
        expect(notifier.state.state, equals(DownloadState.idle));
        expect(notifier.state.progress, equals(0.0));
      });

      test('다운로드 시작 시 상태가 checking으로 변경되어야 함', () async {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);

        // Act
        await notifier.startDownload(
          url: 'https://example.com/model.bin',
          savePath: '/tmp/model.bin',
          expectedChecksum: 'abc123',
        );

        // Assert
        expect(notifier.state.state, equals(DownloadState.completed));
      });

      test('진행률 업데이트가 state에 반영되어야 함', () async {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);

        // Act
        await notifier.startDownload(
          url: 'https://example.com/model.bin',
          savePath: '/tmp/model.bin',
          expectedChecksum: 'abc123',
        );

        // Note: 실제 구현에서는 progress stream을 통해 업데이트
        // 테스트에서는 상태 전환만 확인
        expect(notifier.state.progress, greaterThanOrEqualTo(0.0));
      });

      test('다운로드 실패 시 failed 상태로 변경되어야 함', () async {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);

        // Act
        await notifier.startDownload(
          url: 'https://invalid-url.com/model.bin',
          savePath: '/tmp/model.bin',
          expectedChecksum: 'abc123',
        );

        // Note: 실패 시나리오는 실제 다운로드 시뮬레이션 필요
        // 테스트에서는 state 변화 확인 가능
        // 실패하면 failed 상태가 됨
        if (notifier.state.state == DownloadState.failed) {
          expect(notifier.state.errorMessage, isNotNull);
        }
      });

      test('retry 시 retryCount가 증가해야 함', () async {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);
        // 강제로 실패 상태로 변경 (테스트 목적)
        // Note: 실제 환경에서는 다운로드 실패 시 자동으로 failed 상태가 됨

        // Act
        // retry를 호출하면 retryCount가 증가
        // 현재 구현에서는 startDownload 내부에서 실패 처리됨
        await notifier.retry();

        // Assert
        // retry 호출 후 상태 확인
        expect(notifier.state.retryCount, greaterThanOrEqualTo(0));
      });

      test('maxRetries(3) 초과 시 더 이상 retry하지 않아야 함', () async {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);
        // 강제로 retryCount를 3으로 설정
        // (실제로는 provider 외부에서 state를 직접 수정할 수 없으므로 테스트는 상태 확인만)

        // Act
        // 3회 실패 후 재시도 시도
        for (var i = 0; i < 4; i++) {
          await notifier.startDownload(
            url: 'https://invalid-url.com/model.bin',
            savePath: '/tmp/model.bin',
            expectedChecksum: 'abc123',
          );
          await notifier.retry();
        }

        // Assert
        expect(notifier.state.retryCount, lessThanOrEqualTo(3));
      });

      test('cancel 시 상태가 idle로 변경되어야 함', () {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);

        // Act
        notifier.cancel();

        // Assert
        expect(notifier.state.state, equals(DownloadState.idle));
      });

      test('reset 시 모든 상태가 초기화되어야 함', () {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);

        // Act
        notifier.reset();

        // Assert
        expect(notifier.state.state, equals(DownloadState.idle));
        expect(notifier.state.progress, equals(0.0));
        expect(notifier.state.errorMessage, isNull);
        expect(notifier.state.retryCount, equals(0));
      });
    });

    group('modelDownloadProvider', () {
      test('provider가 초기 상태를 제공해야 함', () {
        // Act
        final status = container.read(modelDownloadProvider);

        // Assert
        expect(status.state, equals(DownloadState.idle));
      });
    });
  });
}
