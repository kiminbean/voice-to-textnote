// 녹음 상태 관리 프로바이더
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:voice_to_textnote/services/background_recording_service.dart';
import 'package:voice_to_textnote/services/recording_recovery_service.dart';

// 녹음 상태 열거형
enum RecordingStatus {
  idle,      // 대기 중
  recording, // 녹음 중
  paused,    // 일시 정지
  stopped,   // 중지됨
}

// 녹음 상태 데이터 클래스
class RecordingState {
  final RecordingStatus status;
  final int elapsedSeconds;
  final String? filePath;

  const RecordingState({
    required this.status,
    required this.elapsedSeconds,
    this.filePath,
  });

  RecordingState copyWith({
    RecordingStatus? status,
    int? elapsedSeconds,
    String? filePath,
  }) {
    return RecordingState(
      status: status ?? this.status,
      elapsedSeconds: elapsedSeconds ?? this.elapsedSeconds,
      filePath: filePath ?? this.filePath,
    );
  }
}

// 녹음 Notifier
class RecordingNotifier extends Notifier<RecordingState> {
  final BackgroundRecordingService _backgroundService = BackgroundRecordingService();
  final RecordingRecoveryService _recoveryService = RecordingRecoveryService();

  @override
  RecordingState build() {
    ref.onDispose(() {
      _backgroundService.dispose();
    });
    return const RecordingState(
      status: RecordingStatus.idle,
      elapsedSeconds: 0,
    );
  }

  Future<void> startRecording() async {
    final dir = await getApplicationDocumentsDirectory();
    final filePath =
        '${dir.path}/meeting_${DateTime.now().millisecondsSinceEpoch}.m4a';

    final config = BackgroundRecordingConfig(
      filePath: filePath,
      flushInterval: const Duration(seconds: 10),
    );

    try {
      await _backgroundService.startRecording(config);
      state = state.copyWith(
        status: RecordingStatus.recording,
        filePath: filePath,
      );
      await _recoveryService.saveActiveRecording(
        filePath,
        startedAt: DateTime.now().toUtc().toIso8601String(),
      );
    } catch (e) {
      state = state.copyWith(status: RecordingStatus.idle);
    }
  }

  Future<void> stopRecording() async {
    try {
      final savedPath = await _backgroundService.stopRecording();
      state = state.copyWith(
        status: RecordingStatus.stopped,
        filePath: savedPath ?? state.filePath,
      );
      await _recoveryService.clearActiveRecording();
    } catch (e) {
      state = state.copyWith(status: RecordingStatus.idle);
    }
  }

  Future<void> pauseRecording() async {
    if (state.status != RecordingStatus.recording) return;
    try {
      await _backgroundService.pauseRecording();
      state = state.copyWith(status: RecordingStatus.paused);
    } catch (_) {}
  }

  Future<void> resumeRecording() async {
    if (state.status != RecordingStatus.paused) return;
    try {
      await _backgroundService.resumeRecording();
      state = state.copyWith(status: RecordingStatus.recording);
    } catch (_) {}
  }

  Future<String?> checkInterruptedRecording() async {
    if (await _recoveryService.hasActiveRecording()) {
      return await _recoveryService.getActiveRecordingPath();
    }
    return null;
  }

  Future<void> discardInterruptedRecording() async {
    await _recoveryService.clearActiveRecording();
    state = const RecordingState(
      status: RecordingStatus.idle,
      elapsedSeconds: 0,
    );
  }

  void reset() {
    state = const RecordingState(
      status: RecordingStatus.idle,
      elapsedSeconds: 0,
    );
  }

  void updateElapsedSeconds(int seconds) {
    state = state.copyWith(elapsedSeconds: seconds);
  }

  void setFilePath(String path) {
    state = state.copyWith(filePath: path);
  }
}

// 녹음 프로바이더
final recordingProvider = NotifierProvider<RecordingNotifier, RecordingState>(
  RecordingNotifier.new,
);
