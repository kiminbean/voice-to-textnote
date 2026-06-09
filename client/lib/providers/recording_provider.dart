// 녹음 상태 관리 프로바이더
// @MX:NOTE: SPEC-APP-005 — pause/resume, audioLevel, RecordingConfig 통합 관리

import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/models/recording_config.dart';
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
  final RecordingConfig recordingConfig;
  final double audioLevel; // 0.0 ~ 1.0 (REQ-002)

  const RecordingState({
    required this.status,
    required this.elapsedSeconds,
    this.filePath,
    this.recordingConfig = RecordingConfig.standard,
    this.audioLevel = 0.0,
  });

  RecordingState copyWith({
    RecordingStatus? status,
    int? elapsedSeconds,
    String? filePath,
    RecordingConfig? recordingConfig,
    double? audioLevel,
  }) {
    return RecordingState(
      status: status ?? this.status,
      elapsedSeconds: elapsedSeconds ?? this.elapsedSeconds,
      filePath: filePath ?? this.filePath,
      recordingConfig: recordingConfig ?? this.recordingConfig,
      audioLevel: audioLevel ?? this.audioLevel,
    );
  }
}

// 녹음 Notifier
class RecordingNotifier extends Notifier<RecordingState> {
  // 백그라운드 녹음 서비스
  final BackgroundRecordingService _backgroundService = BackgroundRecordingService();

  // 오디오 레벨 폴링 타이머 (50ms 간격, REQ-002)
  Timer? _amplitudeTimer;

  // SharedPreferences 키
  static const _qualityIndexKey = 'recording_quality_index';

  @override
  RecordingState build() {
    // Notifier가 해제될 때 리소스 정리
    ref.onDispose(() {
      _backgroundService.dispose();
      _amplitudeTimer?.cancel();
    });

    // 저장된 품질 설정 로드
    _loadSavedConfig();

    return const RecordingState(
      status: RecordingStatus.idle,
      elapsedSeconds: 0,
    );
  }

  /// 저장된 품질 설정 로드
  Future<void> _loadSavedConfig() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final index = prefs.getInt(_qualityIndexKey) ?? 0;
      final config = RecordingConfig.fromIndex(index);
      state = state.copyWith(recordingConfig: config);
    } catch (_) {
      // 로드 실패 시 기본값 유지
    }
  }

  /// 품질 설정 저장 및 업데이트
  Future<void> setRecordingConfig(RecordingConfig config) async {
    // 녹음 중에는 변경 불가 (REQ-004)
    if (state.status == RecordingStatus.recording ||
        state.status == RecordingStatus.paused) {
      return;
    }
    state = state.copyWith(recordingConfig: config);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(_qualityIndexKey, config.presetIndex);
    } catch (_) {
      // 저장 실패 무시
    }
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

    // 백그라운드 녹음 시작 (RecordingConfig 전달)
    try {
      await _backgroundService.startRecording(
        config,
        recordingConfig: state.recordingConfig,
      );
      state = state.copyWith(
        status: RecordingStatus.recording,
        filePath: filePath,
        audioLevel: 0.0,
      );
      _startAmplitudePolling();
    } catch (e) {
      print('녹음 시작 실패: $e');
      state = state.copyWith(status: RecordingStatus.idle);
    }
  }

  // 녹음 일시정지 (REQ-001)
  Future<void> pauseRecording() async {
    if (state.status != RecordingStatus.recording) return;
    try {
      await _backgroundService.pause();
      _amplitudeTimer?.cancel();
      state = state.copyWith(
        status: RecordingStatus.paused,
        audioLevel: 0.0, // 일시정지 시 레벨 0 (REQ-002)
      );
    } catch (e) {
      print('녹음 일시정지 실패: $e');
    }
  }

  // 녹음 재개 (REQ-001)
  Future<void> resumeRecording() async {
    if (state.status != RecordingStatus.paused) return;
    try {
      await _backgroundService.resume();
      state = state.copyWith(status: RecordingStatus.recording);
      _startAmplitudePolling();
    } catch (e) {
      print('녹음 재개 실패: $e');
    }
  }

  // 녹음 중지 - 파일 저장 완료 후 상태 업데이트
  Future<void> stopRecording() async {
    _amplitudeTimer?.cancel();
    try {
      final savedPath = await _backgroundService.stopRecording();
      state = state.copyWith(
        status: RecordingStatus.stopped,
        filePath: savedPath ?? state.filePath,
        audioLevel: 0.0,
      );
    } catch (e) {
      print('녹음 중지 실패: $e');
    }
  }

  // 상태 초기화
  void reset() {
    _amplitudeTimer?.cancel();
    state = RecordingState(
      status: RecordingStatus.idle,
      elapsedSeconds: 0,
      recordingConfig: state.recordingConfig,
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

  /// 오디오 레벨 폴링 시작 (50ms 간격, REQ-002)
  void _startAmplitudePolling() {
    _amplitudeTimer?.cancel();
    _amplitudeTimer = Timer.periodic(
      const Duration(milliseconds: 50),
      (_) async {
        if (state.status == RecordingStatus.recording) {
          final level = await _backgroundService.getAmplitude();
          state = state.copyWith(audioLevel: level);
        }
      },
    );
  }
}

// 녹음 프로바이더
final recordingProvider = NotifierProvider<RecordingNotifier, RecordingState>(
  RecordingNotifier.new,
);
