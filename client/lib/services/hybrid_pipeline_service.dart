import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/offline_task.dart';
import 'package:voice_to_textnote/models/transcription_result.dart';
import 'package:voice_to_textnote/providers/connectivity_provider.dart';
import 'package:voice_to_textnote/providers/offline_stt_provider.dart';
import 'package:voice_to_textnote/services/audio_preprocessor.dart';
import 'package:voice_to_textnote/services/connectivity_service.dart';
import 'package:voice_to_textnote/services/offline_stt_service.dart';
import 'package:voice_to_textnote/services/transcription_api.dart';

/// @MX:SPEC:REQ-MOBILE-009
///
/// 네트워크 상태에 따라 온라인 백엔드 파이프라인과 오프라인 STT를 선택합니다.
class HybridPipelineService {
  final ConnectivityService _connectivityService;
  final AudioPreprocessor _audioPreprocessor;
  final OfflineSttService _offlineSttService;

  final List<OfflineTask> _offlineTasks = [];
  StreamSubscription<ConnectivityStatus>? _connectivitySubscription;

  HybridPipelineService({
    required ConnectivityService connectivityService,
    required AudioPreprocessor audioPreprocessor,
    required OfflineSttService offlineSttService,
  })  : _connectivityService = connectivityService,
        _audioPreprocessor = audioPreprocessor,
        _offlineSttService = offlineSttService;

  bool get isOnline => _connectivityService.isOnline;

  List<OfflineTask> get pendingTasks => List.unmodifiable(
        _offlineTasks.where((task) => task.status == OfflineTaskStatus.pending),
      );

  List<OfflineTask> get failedTasks => List.unmodifiable(
        _offlineTasks.where((task) => task.status == OfflineTaskStatus.failed),
      );

  Future<OfflinePipelineResult> processOffline(String audioPath) async {
    final wavFile = await _audioPreprocessor.convertToWav(audioPath);
    final result =
        await _offlineSttService.transcribeWithProgress(wavFile.path).lastWhere(
              (progress) => progress.status == TranscriptionStatus.completed,
            );

    final transcription = result.result ??
        TranscriptionResult.offline(
          text: '',
          segments: const [],
          language: 'ko',
        );
    final task = _createTask(audioPath, transcription);
    _offlineTasks.add(task);

    return OfflinePipelineResult(
      task: task,
      transcription: transcription.copyWith(offline: true),
    );
  }

  void watchNetworkRecovery(
    Future<String> Function(OfflineTask task) reprocessTask,
  ) {
    _connectivitySubscription ??=
        _connectivityService.onConnectivityStatusChange.listen((status) {
      if (status == ConnectivityStatus.online) {
        reprocessPendingTasks(reprocessTask);
      }
    });
  }

  Future<List<OfflineTask>> reprocessPendingTasks(
    Future<String> Function(OfflineTask task) reprocessTask,
  ) async {
    final updated = <OfflineTask>[];

    for (final task in List<OfflineTask>.from(pendingTasks)) {
      final index = _offlineTasks.indexWhere((item) => item.id == task.id);
      if (index == -1) continue;

      _offlineTasks[index] =
          task.copyWith(status: OfflineTaskStatus.reprocessing);
      try {
        final onlineTaskId = await reprocessTask(task);
        _offlineTasks[index] = _offlineTasks[index].copyWith(
          status: OfflineTaskStatus.completed,
          onlineTranscriptionTaskId: onlineTaskId,
          reprocessedAt: DateTime.now(),
        );
      } catch (e) {
        _offlineTasks[index] = _offlineTasks[index].copyWith(
          status: OfflineTaskStatus.failed,
          errorMessage: e.toString().replaceFirst('Exception: ', ''),
        );
      }
      updated.add(_offlineTasks[index]);
    }

    return updated;
  }

  Future<OfflineTask?> retryTask(
    String taskId,
    Future<String> Function(OfflineTask task) reprocessTask,
  ) async {
    final index = _offlineTasks.indexWhere((task) => task.id == taskId);
    if (index == -1) return null;

    _offlineTasks[index] = _offlineTasks[index].copyWith(
      status: OfflineTaskStatus.pending,
      errorMessage: '',
    );
    final result = await reprocessPendingTasks(reprocessTask);
    for (final task in result) {
      if (task.id == taskId) return task;
    }
    return null;
  }

  void dispose() {
    _connectivitySubscription?.cancel();
    _connectivitySubscription = null;
  }

  OfflineTask _createTask(String audioPath, TranscriptionResult transcription) {
    final id = 'offline-${DateTime.now().microsecondsSinceEpoch}';
    return OfflineTask(
      id: id,
      audioPath: audioPath,
      offlineTranscriptionPath: '$id.json',
      status: OfflineTaskStatus.pending,
      createdAt: transcription.createdAt,
    );
  }
}

class OfflinePipelineResult {
  final OfflineTask task;
  final TranscriptionResult transcription;

  const OfflinePipelineResult({
    required this.task,
    required this.transcription,
  });
}

final audioPreprocessorProvider = Provider<AudioPreprocessor>((ref) {
  return AudioPreprocessor();
});

final hybridPipelineServiceProvider = Provider<HybridPipelineService>((ref) {
  final service = HybridPipelineService(
    connectivityService: ref.watch(connectivityServiceProvider),
    audioPreprocessor: ref.watch(audioPreprocessorProvider),
    offlineSttService: ref.watch(offlineSttServiceProvider),
  );
  ref.onDispose(service.dispose);
  return service;
});

final offlineTaskReprocessorProvider =
    Provider<Future<String> Function(OfflineTask task)>((ref) {
  final transcriptionApi = ref.watch(transcriptionApiProvider);
  return (task) async {
    final response = await transcriptionApi.upload(task.audioPath);
    return response['task_id'] as String;
  };
});
