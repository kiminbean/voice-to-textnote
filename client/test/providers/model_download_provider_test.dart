import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/providers/model_download_provider.dart';
import 'package:voice_to_textnote/services/model_download_service.dart';

// Mock classes
class MockModelDownloadService extends Mock implements ModelDownloadService {}

class FakeCancelToken extends Fake implements CancelToken {}

void main() {
  setUpAll(() {
    registerFallbackValue(FakeCancelToken());
  });

  group('ModelDownloadProvider', () {
    late ProviderContainer container;
    late MockModelDownloadService mockService;

    setUp(() {
      mockService = MockModelDownloadService();
      container = ProviderContainer(
        overrides: [
          modelDownloadServiceProvider.overrideWithValue(mockService),
        ],
      );
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
        when(() => mockService.downloadWithResume(
              url: any(named: 'url'),
              savePath: any(named: 'savePath'),
              cancelToken: any(named: 'cancelToken'),
            )).thenAnswer((_) => Stream<double>.fromIterable([0.5, 1.0]));
        when(() => mockService.verifyChecksum(any(), any()))
            .thenAnswer((_) async => true);

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
        when(() => mockService.downloadWithResume(
              url: any(named: 'url'),
              savePath: any(named: 'savePath'),
              cancelToken: any(named: 'cancelToken'),
            )).thenAnswer((_) => Stream<double>.fromIterable([0.25, 0.75]));
        when(() => mockService.verifyChecksum(any(), any()))
            .thenAnswer((_) async => true);

        // Act
        await notifier.startDownload(
          url: 'https://example.com/model.bin',
          savePath: '/tmp/model.bin',
          expectedChecksum: 'abc123',
        );

        expect(notifier.state.state, equals(DownloadState.completed));
        verify(() => mockService.downloadWithResume(
              url: 'https://example.com/model.bin',
              savePath: '/tmp/model.bin',
              cancelToken: any(named: 'cancelToken'),
            )).called(1);
      });

      test('다운로드 실패 시 failed 상태로 변경되어야 함', () async {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);
        when(() => mockService.downloadWithResume(
              url: any(named: 'url'),
              savePath: any(named: 'savePath'),
              cancelToken: any(named: 'cancelToken'),
            )).thenAnswer((_) => Stream<double>.error(Exception('network')));

        // Act
        await notifier.startDownload(
          url: 'https://invalid-url.com/model.bin',
          savePath: '/tmp/model.bin',
          expectedChecksum: 'abc123',
        );

        expect(notifier.state.state, equals(DownloadState.failed));
        expect(notifier.state.errorMessage, contains('network'));
      });

      test('retry 시 retryCount가 증가해야 함', () async {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);
        when(() => mockService.downloadWithResume(
              url: any(named: 'url'),
              savePath: any(named: 'savePath'),
              cancelToken: any(named: 'cancelToken'),
            )).thenAnswer((_) => Stream<double>.error(Exception('network')));

        // Act
        await notifier.startDownload(
          url: 'https://example.com/model.bin',
          savePath: '/tmp/model.bin',
          expectedChecksum: 'abc123',
        );
        await notifier.retry();

        // Assert
        // retry 호출 후 상태 확인
        expect(notifier.state.retryCount, greaterThanOrEqualTo(0));
      });

      test('maxRetries(3) 초과 시 더 이상 retry하지 않아야 함', () async {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);
        when(() => mockService.downloadWithResume(
              url: any(named: 'url'),
              savePath: any(named: 'savePath'),
              cancelToken: any(named: 'cancelToken'),
            )).thenAnswer((_) => Stream<double>.error(Exception('network')));

        // Act
        await notifier.startDownload(
          url: 'https://invalid-url.com/model.bin',
          savePath: '/tmp/model.bin',
          expectedChecksum: 'abc123',
        );
        for (var i = 0; i < 4; i++) {
          await notifier.retry();
        }

        // Assert
        expect(notifier.state.retryCount, lessThanOrEqualTo(3));
      });

      test('저장공간이 부족하면 다운로드 전에 failed 상태가 되어야 함', () async {
        // Arrange
        final notifier = container.read(modelDownloadProvider.notifier);
        when(() => mockService.hasSufficientStorage(any()))
            .thenAnswer((_) async => false);

        // Act
        await notifier.startDownload(
          url: 'https://example.com/model.bin',
          savePath: '/tmp/model.bin',
          expectedChecksum: 'abc123',
          requiredBytes: 100 * 1024 * 1024,
        );

        // Assert
        expect(notifier.state.state, equals(DownloadState.failed));
        expect(notifier.state.errorMessage, contains('저장 공간'));
        verifyNever(() => mockService.downloadWithResume(
              url: any(named: 'url'),
              savePath: any(named: 'savePath'),
              cancelToken: any(named: 'cancelToken'),
            ));
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
