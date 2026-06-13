// 녹음 상태 관리 프로바이더
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:voice_to_textnote/services/background_recording_service.dart';

// 녹음 상태 열거형
enum RecordingStatus {
  idle, // 대기 중
  recording, // 녹음 중
  paused, // 일시 정지
  stopped, // 중지됨
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
  // 백그라운드 녹음 서비스
  final BackgroundRecordingService _backgroundService =
      BackgroundRecordingService();

  @override
  RecordingState build() {
    // Notifier가 해제될 때 리소스 정리
    ref.onDispose(() {
      _backgroundService.dispose();
    });
    return const RecordingState(
      status: RecordingStatus.idle,
      elapsedSeconds: 0,
    );
  }

  // 녹음 시작 - 백그라운드 녹음 서비스 사용
  Future<void> startRecording() async {
    // 앱 문서 디렉토리에 m4a 파일 경로 생성
    final dir = await getApplicationDocumentsDirectory();
    final filePath =
        '${dir.path}/meeting_${DateTime.now().millisecondsSinceEpoch}.m4a';

    // 백그라운드 녹음 설정
    final config = BackgroundRecordingConfig(
      filePath: filePath,
      flushInterval: const Duration(seconds: 10),
    );

    // 백그라운드 녹음 시작
    try {
      await _backgroundService.startRecording(config);
      state = state.copyWith(
        status: RecordingStatus.recording,
        filePath: filePath,
      );
    } catch (e) {
      print('녹음 시작 실패: $e');
      state = state.copyWith(status: RecordingStatus.idle);
    }
  }

  // 녹음 중지 - 파일 저장 완료 후 상태 업데이트
  Future<void> stopRecording() async {
    try {
      final savedPath = await _backgroundService.stopRecording();
      state = state.copyWith(
        status: RecordingStatus.stopped,
        filePath: savedPath ?? state.filePath,
      );
    } catch (e) {
      print('녹음 중지 실패: $e');
    }
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

  // 파일 경로 설정 (외부에서 직접 설정 시)
  void setFilePath(String path) {
    state = state.copyWith(filePath: path);
  }
}

// 녹음 프로바이더
final recordingProvider = NotifierProvider<RecordingNotifier, RecordingState>(
  RecordingNotifier.new,
);
