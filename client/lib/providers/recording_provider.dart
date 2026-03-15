// 녹음 상태 관리 프로바이더
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
  @override
  RecordingState build() {
    return const RecordingState(
      status: RecordingStatus.idle,
      elapsedSeconds: 0,
    );
  }

  // 녹음 시작
  void startRecording() {
    state = state.copyWith(status: RecordingStatus.recording);
  }

  // 녹음 중지
  void stopRecording() {
    state = state.copyWith(status: RecordingStatus.stopped);
  }

  // 상태 초기화
  void reset() {
    state = const RecordingState(
      status: RecordingStatus.idle,
      elapsedSeconds: 0,
    );
  }

  // 경과 시간 업데이트 (타이머에서 호출)
  void updateElapsedSeconds(int seconds) {
    state = state.copyWith(elapsedSeconds: seconds);
  }

  // 파일 경로 설정 (녹음 완료 후)
  void setFilePath(String path) {
    state = state.copyWith(filePath: path);
  }
}

// 녹음 프로바이더
final recordingProvider = NotifierProvider<RecordingNotifier, RecordingState>(
  RecordingNotifier.new,
);
