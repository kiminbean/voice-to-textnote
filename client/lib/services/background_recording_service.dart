// 백그라운드 녹음 서비스
// @MX:ANCHOR: iOS/Android 플랫폼별 백그라운드 녹음 처리의 중앙 서비스
// @MX:REASON: recording_provider에서 의존하며, iOS audio_session 및 Android Foreground Service 통신 포함

import 'dart:async';
import 'dart:io';
import 'package:audio_session/audio_session.dart';
import 'package:flutter/services.dart';
import 'package:record/record.dart';

/// 백그라운드 녹음 설정
class BackgroundRecordingConfig {
  final String filePath;
  final Duration flushInterval; // 플러시 주기 (기본 10초)

  const BackgroundRecordingConfig({
    required this.filePath,
    this.flushInterval = const Duration(seconds: 10),
  });
}

/// 백그라운드 녹음 서비스
class BackgroundRecordingService {
  AudioRecorder? _recorder;
  Timer? _flushTimer;
  final MethodChannel _methodChannel =
      const MethodChannel('com.voicetextnote.app/recording');

  /// iOS 백그라운드 녹음 초기화
  Future<void> initializeIOS() async {
    if (!Platform.isIOS) return;

    try {
      // AudioSession 설정
      final session = await AudioSession.instance;
      await session.configure(
        const AudioSessionConfiguration(
          avAudioSessionCategory: AVAudioSessionCategory.playAndRecord,
          avAudioSessionCategoryOptions:
              AVAudioSessionCategoryOptions.allowBluetooth,
          avAudioSessionMode: AVAudioSessionMode.defaultMode,
          avAudioSessionRouteSharingPolicy:
              AVAudioSessionRouteSharingPolicy.defaultPolicy,
          avAudioSessionSetActiveOptions: AVAudioSessionSetActiveOptions.none,
          androidAudioAttributes: AndroidAudioAttributes(
            contentType: AndroidAudioContentType.speech,
            flags: AndroidAudioFlags.none,
            usage: AndroidAudioUsage.voiceCommunication,
          ),
          androidAudioFocusGainType: AndroidAudioFocusGainType.gain,
          androidWillPauseWhenDucked: false,
        ),
      );

      // 인터럽트 핸들러 등록
      session.interruptionEventStream.listen(
        (event) {
          if (event.begin) {
            // 인터럽트 시작 (전화 수신 등)
            _handleInterruptionBegin();
          } else {
            // 인터럽트 종료
            _handleInterruptionEnd();
          }
        },
        onError: (error) {
          print('AudioSession 인터럽트 에러: $error');
        },
      );

      print('iOS 백그라운드 녹음 초기화 완료');
    } catch (e) {
      print('iOS 백그라운드 녹음 초기화 실패: $e');
    }
  }

  /// Android 백그라운드 서비스 시작
  Future<void> startAndroidForegroundService() async {
    if (!Platform.isAndroid) return;

    try {
      await _methodChannel.invokeMethod('startForegroundService');
      print('Android Foreground Service 시작 완료');
    } catch (e) {
      print('Android Foreground Service 시작 실패: $e');
    }
  }

  /// Android 백그라운드 서비스 중지
  Future<void> stopAndroidForegroundService() async {
    if (!Platform.isAndroid) return;

    try {
      await _methodChannel.invokeMethod('stopForegroundService');
      print('Android Foreground Service 중지 완료');
    } catch (e) {
      print('Android Foreground Service 중지 실패: $e');
    }
  }

  /// 백그라운드 녹음 시작
  Future<void> startRecording(BackgroundRecordingConfig config) async {
    _recorder = AudioRecorder();

    // 플랫폼별 초기화
    if (Platform.isIOS) {
      await initializeIOS();
    } else if (Platform.isAndroid) {
      await startAndroidForegroundService();
    }

    // 권한 확인
    if (!await _recorder!.hasPermission()) {
      throw Exception('마이크 권한이 거부됨');
    }

    // 녹음 시작
    await _recorder!.start(
      const RecordConfig(encoder: AudioEncoder.aacLc),
      path: config.filePath,
    );

    // 주기적 플러시 타이머 시작 (크래시 방지)
    _startFlushTimer(config.flushInterval);
  }

  /// 백그라운드 녹음 중지
  Future<String?> stopRecording() async {
    _flushTimer?.cancel();

    final savedPath = await _recorder?.stop();
    _recorder?.dispose();
    _recorder = null;

    // Android Foreground Service 중지
    if (Platform.isAndroid) {
      await stopAndroidForegroundService();
    }

    return savedPath;
  }

  /// 주기적 플러시 타이머 (크래시 방지)
  void _startFlushTimer(Duration interval) {
    _flushTimer?.cancel();
    _flushTimer = Timer.periodic(interval, (_) {
      // 녹음 중일 때만 플러시
      if (_recorder != null) {
        _performFlush();
      }
    });
  }

  /// 실제 플러시 수행
  Future<void> _performFlush() async {
    try {
      // iOS: audio_session을 통해 현재 세션 갱신
      if (Platform.isIOS) {
        final session = await AudioSession.instance;
        await session.setActive(true);
        print('iOS 주기적 플러시 완료');
      }

      // Android: 네이티브 서비스에 플러시 요청
      if (Platform.isAndroid) {
        await _methodChannel.invokeMethod('flushRecording');
        print('Android 주기적 플러시 완료');
      }
    } catch (e) {
      print('주기적 플러시 실패: $e');
    }
  }

  /// 인터럽트 시작 처리 (iOS)
  void _handleInterruptionBegin() async {
    print('Audio 인터럽트 시작 - 녹음 일시 정지');
    // 네이티브 레코더는 시스템에 의해 자동으로 일시 정지됨
  }

  /// 인터럽트 종료 처리 (iOS)
  void _handleInterruptionEnd() async {
    print('Audio 인터럽트 종료 - 녹음 재개');
    try {
      final session = await AudioSession.instance;
      await session.setActive(true);
    } catch (e) {
      print('인터럽트 종료 후 세션 활성화 실패: $e');
    }
  }

  /// 녹음 상태 확인
  Future<bool> isRecording() async {
    return _recorder != null && await _recorder!.isRecording();
  }

  /// 리소스 정리
  void dispose() {
    _flushTimer?.cancel();
    _recorder?.dispose();
    _recorder = null;
  }
}
