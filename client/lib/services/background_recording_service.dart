// 백그라운드 녹음 서비스
// @MX:ANCHOR: iOS/Android 플랫폼별 백그라운드 녹음 처리의 중앙 서비스
// @MX:REASON: recording_provider에서 의존하며, iOS audio_session 및 Android Foreground Service 통신 포함
//
// SPEC-MOBILE-005 변경사항:
// - G3/G4: 인터럽션 시 실제 recorder pause/resume 수행
// - G7: RecordConfig 음성 최적화 설정 (mono, AGC, echo cancel, noise suppress)
// - G6: 라우트 변경 감지 및 처리
// - G1/G13: iOS MethodChannel startBackgroundTask/stopBackgroundTask/flushRecording 호출

import 'dart:async';
import 'dart:io';
import 'package:audio_session/audio_session.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:record/record.dart';

/// 백그라운드 녹음 설정
class BackgroundRecordingConfig {
  final String filePath;
  final Duration flushInterval;

  const BackgroundRecordingConfig({
    required this.filePath,
    this.flushInterval = const Duration(seconds: 10),
  });
}

/// 인터럽션 상태 (Dart→Provider 전달용)
enum InterruptionState {
  /// 녹음 중 (인터럽션 없음)
  active,
  /// 인터럽션 발생으로 일시정지됨
  interrupted,
}

/// 백그라운드 녹음 서비스
class BackgroundRecordingService {
  AudioRecorder? _recorder;
  Timer? _flushTimer;

  final MethodChannel _methodChannel =
      const MethodChannel('com.voicetextnote.app/recording');

  // 인터럽션 중복 방지 (audio_session + 네이티브 이벤트 de-duplicate)
  bool _isInterrupted = false;

  // 구독 관리
  StreamSubscription? _interruptionSub;
  StreamSubscription? _deviceChangedSub;
  bool _nativeHandlerRegistered = false;

  /// 인터럽션 상태 변경 콜백 (Provider에서 구독)
  void Function(InterruptionState state)? onInterruptionChanged;

  /// 라우트 변경 콜백 (예: 헤드셋 연결/해제)
  void Function(String reason)? onRouteChanged;

  // ──────────────────────────────────────────────
  // REQ-001: iOS 백그라운드 태스크 + MethodChannel
  // ──────────────────────────────────────────────

  /// iOS 백그라운드 녹음 초기화
  Future<void> initializeIOS() async {
    if (!Platform.isIOS) return;

    try {
      final session = await AudioSession.instance;
      await session.configure(
        const AudioSessionConfiguration(
          avAudioSessionCategory: AVAudioSessionCategory.playAndRecord,
          avAudioSessionCategoryOptions:
              AVAudioSessionCategoryOptions.allowBluetooth,
          avAudioSessionMode: AVAudioSessionMode.defaultMode,
          avAudioSessionRouteSharingPolicy:
              AVAudioSessionRouteSharingPolicy.defaultPolicy,
          avAudioSessionSetActiveOptions:
              AVAudioSessionSetActiveOptions.none,
          androidAudioAttributes: AndroidAudioAttributes(
            contentType: AndroidAudioContentType.speech,
            flags: AndroidAudioFlags.none,
            usage: AndroidAudioUsage.voiceCommunication,
          ),
          androidAudioFocusGainType: AndroidAudioFocusGainType.gain,
          androidWillPauseWhenDucked: false,
        ),
      );

      // G3/G4: 인터럽션 스트림 구독 (실제 pause/resume 수행)
      _interruptionSub = session.interruptionEventStream.listen(
        (event) {
          if (event.begin) {
            _handleInterruptionBegin();
          } else {
            _handleInterruptionEnd();
          }
        },
        onError: (error) {
          debugPrint('AudioSession 인터럽트 에러: $error');
        },
      );

      // G6: 라우트 변경 감지
      _deviceChangedSub = session.devicesChangedEventStream.listen(
        (_) {
          // devicesChanged 트리거 — 네이티브에서 더 상세한 reason을 제공
          debugPrint('오디오 디바이스 변경 감지');
        },
        onError: (error) {
          debugPrint('디바이스 변경 감지 에러: $error');
        },
      );

      // 네이티브→Dart 이벤트 핸들러 등록 (중복 처리 방지 포함)
      _registerNativeEventHandler();

      debugPrint('iOS 백그라운드 녹음 초기화 완료');
    } catch (e) {
      debugPrint('iOS 백그라운드 녹음 초기화 실패: $e');
    }
  }

  /// 네이티브→Dart 이벤트 핸들러 등록
  /// AppDelegate에서 전달하는 인터럽션/라우트 변경 이벤트 수신
  void _registerNativeEventHandler() {
    if (_nativeHandlerRegistered) return;
    _nativeHandlerRegistered = true;

    _methodChannel.setMethodCallHandler((call) async {
      switch (call.method) {
        case 'onInterruptionBegin':
          // audio_session과 중복 방지
          _handleInterruptionBegin();
          break;
        case 'onInterruptionEnd':
          // shouldResume 플래그 추출 (bool 또는 Map)
          final shouldResume = _extractShouldResume(call.arguments);
          _handleInterruptionEnd(shouldResume: shouldResume);
          break;
        case 'onRouteChange':
          final reason = _extractRouteReason(call.arguments);
          onRouteChanged?.call(reason);
          debugPrint('라우트 변경: $reason');
          break;
        default:
          break;
      }
      return null;
    });
  }

  /// shouldResume 플래그 추출
  bool _extractShouldResume(dynamic arguments) {
    if (arguments is bool) return arguments;
    if (arguments is Map) {
      return arguments['shouldResume'] as bool? ?? false;
    }
    return false;
  }

  /// 라우트 변경 사유 추출
  String _extractRouteReason(dynamic arguments) {
    if (arguments is Map) {
      return arguments['reason'] as String? ?? 'unknown';
    }
    return 'unknown';
  }

  // ──────────────────────────────────────────────
  // Android Foreground Service
  // ──────────────────────────────────────────────

  /// Android 백그라운드 서비스 시작
  Future<void> startAndroidForegroundService() async {
    if (!Platform.isAndroid) return;

    try {
      await _methodChannel.invokeMethod('startForegroundService');
      debugPrint('Android Foreground Service 시작 완료');
    } catch (e) {
      debugPrint('Android Foreground Service 시작 실패: $e');
    }
  }

  /// Android 백그라운드 서비스 중지
  Future<void> stopAndroidForegroundService() async {
    if (!Platform.isAndroid) return;

    try {
      await _methodChannel.invokeMethod('stopForegroundService');
      debugPrint('Android Foreground Service 중지 완료');
    } catch (e) {
      debugPrint('Android Foreground Service 중지 실패: $e');
    }
  }

  // ──────────────────────────────────────────────
  // 녹음 시작/중지
  // ──────────────────────────────────────────────

  /// 백그라운드 녹음 시작
  Future<void> startRecording(BackgroundRecordingConfig config) async {
    _recorder = AudioRecorder();

    // 플랫폼별 초기화
    if (Platform.isIOS) {
      await initializeIOS();
      // G1: iOS 백그라운드 태스크 시작
      try {
        await _methodChannel.invokeMethod('startBackgroundTask');
      } catch (e) {
        debugPrint('iOS 백그라운드 태스크 시작 실패 (무시 가능): $e');
      }
    } else if (Platform.isAndroid) {
      await startAndroidForegroundService();
    }

    // 권한 확인
    if (!await _recorder!.hasPermission()) {
      throw Exception('마이크 권한이 거부됨');
    }

    // G7: 음성 최적화 RecordConfig
    await _recorder!.start(
      _buildSpeechOptimizedConfig(),
      path: config.filePath,
    );

    // 인터럽션 상태 초기화
    _isInterrupted = false;

    // 주기적 플러시 타이머 시작 (크래시 방지)
    _startFlushTimer(config.flushInterval);
  }

  /// G7: 음성 녹음 최적화 RecordConfig 생성
  /// - mono (음성은 단일 채널로 충분, 파일 크기 절반)
  /// - autoGain (자동 볼륨 조정)
  /// - echoCancel (에코 제거)
  /// - noiseSuppress (노이즈 억제)
  RecordConfig _buildSpeechOptimizedConfig() {
    return const RecordConfig(
      encoder: AudioEncoder.aacLc,
      bitRate: 128000,
      sampleRate: 44100,
      numChannels: 1, // mono — 음성 녹음에 최적
      autoGain: true,
      echoCancel: true,
      noiseSuppress: true,
      iosConfig: IosRecordConfig(
        categoryOptions: [
          IosAudioCategoryOption.defaultToSpeaker,
          IosAudioCategoryOption.allowBluetooth,
          IosAudioCategoryOption.allowBluetoothA2DP,
        ],
      ),
    );
  }

  /// 녹음 일시정지 (T-012 / 수동)
  Future<void> pauseRecording() async {
    if (_recorder == null) return;
    try {
      await _recorder!.pause();
    } catch (e) {
      // 일부 플랫폼에서 pause 미지원 시 무시
    }
  }

  /// 녹음 재개 (T-012 / 수동)
  Future<void> resumeRecording() async {
    if (_recorder == null) return;
    try {
      await _recorder!.resume();
    } catch (e) {
      // 일부 플랫폼에서 resume 미지원 시 무시
    }
  }

  /// 백그라운드 녹음 중지
  Future<String?> stopRecording() async {
    _flushTimer?.cancel();

    final savedPath = await _recorder?.stop();
    _recorder?.dispose();
    _recorder = null;

    if (Platform.isIOS) {
      // G1: iOS 백그라운드 태스크 중지
      try {
        await _methodChannel.invokeMethod('stopBackgroundTask');
      } catch (e) {
        debugPrint('iOS 백그라운드 태스크 중지 실패 (무시 가능): $e');
      }
    } else if (Platform.isAndroid) {
      await stopAndroidForegroundService();
    }

    return savedPath;
  }

  // ──────────────────────────────────────────────
  // 주기적 플러시
  // ──────────────────────────────────────────────

  /// 주기적 플러시 타이머 (크래시 방지)
  void _startFlushTimer(Duration interval) {
    _flushTimer?.cancel();
    _flushTimer = Timer.periodic(interval, (_) {
      if (_recorder != null) {
        _performFlush();
      }
    });
  }

  /// 실제 플러시 수행
  Future<void> _performFlush() async {
    try {
      if (Platform.isIOS) {
        // audio_session 세션 갱신
        final session = await AudioSession.instance;
        await session.setActive(true);

        // G13: 네이티브 flushRecording 호출 (세션 활성 상태 재확인)
        try {
          await _methodChannel.invokeMethod('flushRecording');
        } catch (_) {
          // MissingPluginException은 무시 (테스트 환경 등)
        }
      }

      if (Platform.isAndroid) {
        await _methodChannel.invokeMethod('flushRecording');
      }
    } catch (e) {
      debugPrint('주기적 플러시 실패: $e');
    }
  }

  // ──────────────────────────────────────────────
  // G3/G4: 인터럽션 처리 (실제 pause/resume)
  // ──────────────────────────────────────────────

  /// 인터럽션 시작 처리 — 녹음을 실제로 일시정지
  void _handleInterruptionBegin() {
    // 중복 이벤트 방지 (audio_session + 네이티브)
    if (_isInterrupted) return;
    _isInterrupted = true;

    debugPrint('Audio 인터럽트 시작 - 녹음 일시정지');

    // 실제 recorder pause 수행
    _recorder?.pause().catchError((e) {
      debugPrint('인터럽션 pause 실패: $e');
    });

    onInterruptionChanged?.call(InterruptionState.interrupted);
  }

  /// 인터럽션 종료 처리 — 녹음 재개
  /// [shouldResume]: iOS에서 인터럽션 종료 후 재개 가능 여부 힌트
  void _handleInterruptionEnd({bool shouldResume = true}) {
    if (!_isInterrupted) return;
    _isInterrupted = false;

    debugPrint('Audio 인터럽트 종료 - 녹음 재개 시도 (shouldResume: $shouldResume)');

    // 세션 재활성화
    _reactivateSession().then((_) {
      if (shouldResume) {
        // 실제 recorder resume 수행
        _recorder?.resume().catchError((e) {
          debugPrint('인터럽션 후 resume 실패: $e');
        });
      }
    });

    onInterruptionChanged?.call(InterruptionState.active);
  }

  /// 오디오 세션 재활성화
  Future<void> _reactivateSession() async {
    try {
      final session = await AudioSession.instance;
      await session.setActive(true);
    } catch (e) {
      debugPrint('인터럽션 종료 후 세션 활성화 실패: $e');
    }
  }

  // ──────────────────────────────────────────────
  // 유틸리티
  // ──────────────────────────────────────────────

  /// 현재 인터럽션 상태 확인
  bool get isInterrupted => _isInterrupted;

  /// 녹음 상태 확인
  Future<bool> isRecording() async {
    return _recorder != null && await _recorder!.isRecording();
  }

  /// 리소스 정리
  void dispose() {
    _flushTimer?.cancel();
    _interruptionSub?.cancel();
    _deviceChangedSub?.cancel();
    // 바인딩 미초기화 상태 (단위 테스트 등)에서도 안전하게 동작
    try {
      _methodChannel.setMethodCallHandler(null);
    } catch (_) {
      // 바인딩이 초기화되지 않은 경우 — 무시
    }
    _nativeHandlerRegistered = false;
    _recorder?.dispose();
    _recorder = null;
  }
}
