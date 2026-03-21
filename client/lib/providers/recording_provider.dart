// 녹음 상태 관리 프로바이더
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

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
  // 실제 오디오 레코더 인스턴스 (record 패키지)
  AudioRecorder? _recorder;

  @override
  RecordingState build() {
    // Notifier가 해제될 때 레코더 리소스 정리
    ref.onDispose(() {
      _recorder?.dispose();
    });
    return const RecordingState(
      status: RecordingStatus.idle,
      elapsedSeconds: 0,
    );
  }

  // 녹음 시작 - 마이크 권한 확인 후 실제 녹음 시작
  // iOS 동작: hasPermission() 최초 호출 시 시스템 권한 다이얼로그를 표시하고 false를 반환함.
  // 사용자가 권한을 허용하면 다음 호출부터 true를 반환.
  // UX 개선을 위해 RecordingScreen 진입 시 proactivePermissionCheck()를 호출하는 것을 권장.
  Future<void> startRecording() async {
    _recorder = AudioRecorder();

    // 마이크 권한 확인 (iOS: 최초 실행 시 다이얼로그 표시 후 false 반환 → 사용자가 허용 후 재시도)
    if (!await _recorder!.hasPermission()) {
      _recorder!.dispose();
      _recorder = null;
      return;
    }

    // 앱 문서 디렉토리에 m4a 파일 경로 생성
    final dir = await getApplicationDocumentsDirectory();
    final filePath =
        '${dir.path}/meeting_${DateTime.now().millisecondsSinceEpoch}.m4a';

    // AAC-LC 인코더로 녹음 시작
    await _recorder!.start(
      const RecordConfig(encoder: AudioEncoder.aacLc),
      path: filePath,
    );

    state = state.copyWith(
      status: RecordingStatus.recording,
      filePath: filePath,
    );
  }

  // 녹음 중지 - 파일 저장 완료 후 상태 업데이트
  Future<void> stopRecording() async {
    // stop()은 저장된 파일 경로를 반환
    final savedPath = await _recorder?.stop();
    _recorder?.dispose();
    _recorder = null;

    state = state.copyWith(
      status: RecordingStatus.stopped,
      // stop()이 반환한 경로를 사용하되, 없으면 기존 filePath 유지
      filePath: savedPath ?? state.filePath,
    );
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
