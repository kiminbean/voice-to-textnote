// SPEC-MOBILE-002: 하이브리드 STT 파이프라인 프로바이더
//
// 온라인 → 서버 STT (기존 pipeline_provider 사용)
// 오프라인 + 모델 설치 → 로컬 STT → 재처리 큐 적재
// 오프라인 + 모델 미설치 → 에러
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/transcription_source.dart';
import 'package:voice_to_textnote/providers/connectivity_provider.dart';
import 'package:voice_to_textnote/providers/pipeline_provider.dart';
import 'package:voice_to_textnote/services/local_stt_service.dart';
import 'package:voice_to_textnote/services/reprocess_queue.dart';
import 'package:voice_to_textnote/services/transcription_api.dart';

/// 하이브리드 파이프라인 처리 결과
class HybridPipelineResult {
  final TranscriptionSource source;
  final String? serverTaskId;
  final String? localText;
  final String? errorMessage;

  const HybridPipelineResult({
    required this.source,
    this.serverTaskId,
    this.localText,
    this.errorMessage,
  });

  bool get isSuccess => errorMessage == null;
}

/// 하이브리드 파이프라인 상태
enum HybridPipelineState { idle, processing, completed, failed }

class HybridPipelineStatus {
  final HybridPipelineState state;
  final TranscriptionSource? source;
  final String? errorMessage;

  const HybridPipelineStatus({
    required this.state,
    this.source,
    this.errorMessage,
  });

  const HybridPipelineStatus.initial()
      : state = HybridPipelineState.idle,
        source = null,
        errorMessage = null;
}

final hybridPipelineProvider =
    StateNotifierProvider<HybridPipelineNotifier, HybridPipelineStatus>((ref) {
  return HybridPipelineNotifier(ref);
});

class HybridPipelineNotifier extends StateNotifier<HybridPipelineStatus> {
  final Ref _ref;

  HybridPipelineNotifier(this._ref) : super(const HybridPipelineStatus.initial());

  /// 하이브리드 전사 처리 진입점
  ///
  /// 1. 연결 상태 확인 (connectivityProvider)
  /// 2. 온라인 → 기존 서버 파이프라인 위임
  /// 3. 오프라인 → 로컬 STT 시도 → 재처리 큐 적재
  Future<HybridPipelineResult> transcribe(
    String audioFilePath, {
    String? templateId,
    String? vocabularyId,
  }) async {
    state = const HybridPipelineStatus(
      state: HybridPipelineState.processing,
    );

    final isOnline = _ref.read(connectivityProvider);
    final localStt = _ref.read(localSttServiceProvider);

    try {
      if (isOnline) {
        return await _processOnline(
          audioFilePath,
          templateId: templateId,
          vocabularyId: vocabularyId,
        );
      }

      // 오프라인: 로컬 모델 확인
      final modelReady = await localStt.isAvailable();
      if (!modelReady) {
        state = const HybridPipelineStatus(
          state: HybridPipelineState.failed,
          errorMessage: '오프라인 상태이며 오프라인 STT 모델이 설치되어 있지 않습니다',
        );
        return const HybridPipelineResult(
          source: TranscriptionSource.server,
          errorMessage: '오프라인 상태이며 오프라인 STT 모델이 설치되어 있지 않습니다',
        );
      }

      return await _processOffline(audioFilePath);
    } catch (e) {
      state = HybridPipelineStatus(
        state: HybridPipelineState.failed,
        errorMessage: e.toString(),
      );
      return HybridPipelineResult(
        source: isOnline ? TranscriptionSource.server : TranscriptionSource.local,
        errorMessage: e.toString(),
      );
    }
  }

  /// 온라인 처리: 기존 서버 파이프라인에 위임
  Future<HybridPipelineResult> _processOnline(
    String audioFilePath, {
    String? templateId,
    String? vocabularyId,
  }) async {
    final pipeline = _ref.read(pipelineProvider.notifier);

    state = const HybridPipelineStatus(
      state: HybridPipelineState.processing,
      source: TranscriptionSource.server,
    );

    await pipeline.startPipeline(
      audioFilePath,
      templateId: templateId,
      vocabularyId: vocabularyId,
    );

    final pipelineState = _ref.read(pipelineProvider);

    if (pipelineState.currentStep.name == 'failed') {
      state = HybridPipelineStatus(
        state: HybridPipelineState.failed,
        source: TranscriptionSource.server,
        errorMessage: pipelineState.errorMessage ?? '서버 처리 실패',
      );
      return HybridPipelineResult(
        source: TranscriptionSource.server,
        errorMessage: pipelineState.errorMessage,
      );
    }

    state = const HybridPipelineStatus(
      state: HybridPipelineState.completed,
      source: TranscriptionSource.server,
    );

    return HybridPipelineResult(
      source: TranscriptionSource.server,
      serverTaskId: pipelineState.minutesTaskId,
    );
  }

  /// 오프라인 처리: 로컬 STT → 재처리 큐 적재
  Future<HybridPipelineResult> _processOffline(String audioFilePath) async {
    final localStt = _ref.read(localSttServiceProvider);

    state = const HybridPipelineStatus(
      state: HybridPipelineState.processing,
      source: TranscriptionSource.local,
    );

    final result = await localStt.transcribe(audioFilePath);

    // 로컬 전사 결과를 재처리 큐에 적재
    final queue = _ref.read(reprocessQueueProvider);
    final offlineTaskId = 'offline_${DateTime.now().millisecondsSinceEpoch}';
    await queue.enqueue(
      taskId: offlineTaskId,
      audioFilePath: audioFilePath,
      localText: result.text,
    );

    state = const HybridPipelineStatus(
      state: HybridPipelineState.completed,
      source: TranscriptionSource.local,
    );

    return HybridPipelineResult(
      source: TranscriptionSource.local,
      localText: result.text,
    );
  }

  /// 네트워크 복구 시 재처리 큐 비우기
  ///
  /// 큐에 있는 오프라인 전사 결과들을 서버로 재전송하여
  /// 고품질 전사로 교체한다.
  Future<int> drainReprocessQueue() async {
    final queue = _ref.read(reprocessQueueProvider);
    if (queue.isEmpty) return 0;

    await queue.load();
    int processedCount = 0;

    while (!queue.isEmpty) {
      final item = queue.peek();
      if (item == null) break;

      await queue.markProcessing(item.taskId);

      try {
        // 서버로 오디오 재전송
        final sttApi = _ref.read(transcriptionApiProvider);
        await sttApi.upload(item.audioFilePath);

        // 서버 전사 완료 후 큐에서 제거
        await queue.remove(item.taskId);
        processedCount++;
      } catch (_) {
        // 실패 시 다음 시도를 위해 processing 플래그 리셋하지 않음
        // (isProcessing 항목은 peek에서 제외되므로 무한 루프 방지)
        break;
      }
    }

    return processedCount;
  }

  void reset() {
    state = const HybridPipelineStatus.initial();
  }
}
