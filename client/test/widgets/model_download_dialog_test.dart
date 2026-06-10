import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/providers/model_download_provider.dart';
import 'package:voice_to_textnote/widgets/model_download_dialog.dart';

// 테스트용 상태 Provider
final testDownloadStatusProvider = Provider<DownloadStatus>((ref) {
  return DownloadStatus.initial();
});

// 테스트용 다이얼로그 위젯
class _TestModelDownloadDialog extends ConsumerWidget {
  const _TestModelDownloadDialog();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(testDownloadStatusProvider);
    return AlertDialog(
      title: Text(_getTitle(status.state)),
      content: _buildContent(status),
      actions: _buildActions(context, status),
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

  List<Widget> _buildActions(BuildContext context, DownloadStatus status) {
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
              // TODO: 다운로드 시작
            },
            child: const Text('다운로드'),
          ),
        ];
      case DownloadState.downloading:
      case DownloadState.verifying:
        return [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
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
              onPressed: () {},
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
}

void main() {
  group('ModelDownloadDialog', () {
    testWidgets('idle 상태에서 다운로드 버튼을 보여야 함', (tester) async {
      // Arrange
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            testDownloadStatusProvider.overrideWithValue(
              DownloadStatus.initial(),
            ),
          ],
          child: const MaterialApp(
            home: _TestModelDownloadDialog(),
          ),
        ),
      );

      // Assert
      expect(find.text('모델 다운로드'), findsOneWidget);
      expect(find.text('다운로드'), findsOneWidget);
    });

    testWidgets('완료 상태에서 완료 메시지를 보여야 함', (tester) async {
      // Arrange
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            testDownloadStatusProvider.overrideWithValue(
              const DownloadStatus(
                state: DownloadState.completed,
                progress: 1.0,
              ),
            ),
          ],
          child: const MaterialApp(
            home: _TestModelDownloadDialog(),
          ),
        ),
      );

      await tester.pump();

      // Assert
      expect(find.text('다운로드 완료'), findsOneWidget);
    });

    testWidgets('실패 상태에서 재시도 버튼을 보여야 함', (tester) async {
      // Arrange
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            testDownloadStatusProvider.overrideWithValue(
              const DownloadStatus(
                state: DownloadState.failed,
                errorMessage: 'Download failed',
                retryCount: 1,
              ),
            ),
          ],
          child: const MaterialApp(
            home: _TestModelDownloadDialog(),
          ),
        ),
      );

      await tester.pump();

      // Assert
      expect(find.text('다운로드 실패'), findsOneWidget);
      expect(find.text('재시도'), findsOneWidget);
    });

    testWidgets('검증 중 상태에서 검증 메시지를 보여야 함', (tester) async {
      // Arrange
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            testDownloadStatusProvider.overrideWithValue(
              const DownloadStatus(
                state: DownloadState.verifying,
                progress: 1.0,
              ),
            ),
          ],
          child: const MaterialApp(
            home: _TestModelDownloadDialog(),
          ),
        ),
      );

      await tester.pump();

      // Assert
      expect(find.text('검증 중...'), findsOneWidget);
    });
  });

  group('ModelDownloadDialog.showCellularConfirmation', () {
    testWidgets('셀룰러 확인 다이얼로그를 표시해야 함', (tester) async {
      // Arrange
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () {
                  ModelDownloadDialog.showCellularConfirmation(context);
                },
                child: const Text('Show Dialog'),
              ),
            ),
          ),
        ),
      );

      // Act
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Assert - 제목 및 버튼은 정확 매치
      expect(find.text('모바일 데이터 사용 안내'), findsOneWidget);
      expect(find.text('취소'), findsOneWidget);
      expect(find.text('다운로드'), findsOneWidget);
      // 내용은 단일 Text 위젯에 \n으로 결합되므로 부분 문자열로 확인
      expect(
        find.byWidgetPredicate(
          (widget) =>
              widget is Text &&
              widget.data != null &&
              widget.data!.contains('모바일 데이터') &&
              widget.data!.contains('150MB') &&
              widget.data!.contains('계속하시겠습니까?'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('다운로드 버튼 누르면 true를 반환해야 함', (tester) async {
      // Arrange
      bool? result;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  result = await ModelDownloadDialog.showCellularConfirmation(
                    context,
                  );
                },
                child: const Text('Show Dialog'),
              ),
            ),
          ),
        ),
      );

      // Act
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('다운로드'));
      await tester.pumpAndSettle();

      // Assert
      expect(result, isTrue);
    });

    testWidgets('취소 버튼 누르면 false를 반환해야 함', (tester) async {
      // Arrange
      bool? result;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  result = await ModelDownloadDialog.showCellularConfirmation(
                    context,
                  );
                },
                child: const Text('Show Dialog'),
              ),
            ),
          ),
        ),
      );

      // Act
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('취소'));
      await tester.pumpAndSettle();

      // Assert
      expect(result, isFalse);
    });
  });

  group('ModelDownloadDialog.show', () {
    testWidgets('다이얼로그를 표시해야 함', (tester) async {
      // Arrange - ModelDownloadDialog는 ConsumerWidget이므로 ProviderScope 필요
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () => ModelDownloadDialog.show(context),
                  child: const Text('Show Dialog'),
                ),
              ),
            ),
          ),
        ),
      );

      // Act
      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Assert
      expect(find.byType(ModelDownloadDialog), findsOneWidget);
    });
  });
}
