import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart';
import 'package:voice_to_textnote/models/transcription_result.dart';
import 'package:whisper_ggml_plus/whisper_ggml_plus.dart';

/// 플랫폼별 STT 엔진 정보
class EngineInfo {
  /// 엔진 이름 (예: "whisper.cpp", "mlx-whisper")
  final String name;

  /// 플랫폼 (예: "ios", "android", "macos")
  final String platform;

  /// 가속기 (예: "coreml", "tflite", "mps")
  final String? accelerator;

  /// 모델 버전 (예: "whisper-base")
  final String modelVersion;

  const EngineInfo({
    required this.name,
    required this.platform,
    required this.modelVersion,
    this.accelerator,
  });

  @override
  String toString() {
    return 'EngineInfo(name: $name, platform: $platform, accelerator: $accelerator, modelVersion: $modelVersion)';
  }
}

/// STT 처리 중 발생하는 도메인 예외
class SttException implements Exception {
  /// 에러 메시지
  final String message;

  /// 에러 코드 (선택)
  final String? code;

  const SttException(this.message, {this.code});

  @override
  String toString() {
    if (code != null) {
      return 'SttException(code: $code, message: $message)';
    }
    return 'SttException: $message';
  }
}

/// 네이티브 STT 엔진 추상 인터페이스
abstract class PlatformSttService {
  /// 오디오 파일을 전사하고 결과를 반환
  Future<TranscriptionResult> transcribe(
    String audioPath, {
    String language = 'ko',
  });

  /// STT 엔진 사용 가능 여부 확인
  Future<bool> isAvailable();

  /// STT 엔진 정보 반환
  Future<EngineInfo> getEngineInfo();

  /// 전사 진행률 스트림 (0.0 ~ 1.0)
  Stream<double> get progressStream;
}

/// MethodChannel 기반 STT 서비스 구현
@Deprecated('Use WhisperSttServiceImpl instead. MethodChannel STT is legacy.')
class PlatformSttServiceImpl implements PlatformSttService {
  static const _channelName = 'com.voicetextnote/whisper_stt';
  static const _eventChannelName = 'com.voicetextnote/whisper_stt_progress';

  final MethodChannel _methodChannel;
  final EventChannel _eventChannel;

  PlatformSttServiceImpl()
      : _methodChannel = const MethodChannel(_channelName),
        _eventChannel = const EventChannel(_eventChannelName);

  @override
  Future<TranscriptionResult> transcribe(
    String audioPath, {
    String language = 'ko',
  }) async {
    try {
      final result = await _methodChannel.invokeMethod('transcribe', {
        'audio_path': audioPath,
        'language': language,
      });

      if (result == null) {
        throw const SttException('Transcription returned null');
      }

      return TranscriptionResult.fromJson(result as Map<String, dynamic>);
    } on PlatformException catch (e) {
      throw SttException(
        e.message ?? 'Unknown platform exception',
        code: e.code,
      );
    } on Exception catch (e) {
      throw SttException('Transcription failed: ${e.toString()}');
    }
  }

  @override
  Future<bool> isAvailable() async {
    try {
      final result = await _methodChannel.invokeMethod('isAvailable');
      return result == true;
    } on PlatformException catch (e) {
      throw SttException(
        e.message ?? 'Failed to check availability',
        code: e.code,
      );
    }
  }

  @override
  Future<EngineInfo> getEngineInfo() async {
    try {
      final result = await _methodChannel.invokeMethod('getEngineInfo');

      if (result == null) {
        throw const SttException('Engine info returned null');
      }

      final map = result as Map<String, dynamic>;
      return EngineInfo(
        name: map['name'] as String,
        platform: map['platform'] as String,
        modelVersion: map['model_version'] as String,
        accelerator: map['accelerator'] as String?,
      );
    } on PlatformException catch (e) {
      throw SttException(
        e.message ?? 'Failed to get engine info',
        code: e.code,
      );
    }
  }

  @override
  Stream<double> get progressStream {
    try {
      return _eventChannel
          .receiveBroadcastStream()
          .map((event) => (event as num).toDouble());
    } on Exception catch (e) {
      throw SttException('Failed to create progress stream: ${e.toString()}');
    }
  }
}

/// whisper_ggml_plus 기반 STT 서비스 구현
class WhisperSttServiceImpl implements PlatformSttService {
  static const _model = WhisperModel.base;

  WhisperController? _controller;
  bool _isInitialized = false;

  /// WhisperController를 지연 생성하여 앱 시작 비용을 줄입니다.
  Future<WhisperController> _getController() async {
    if (_isInitialized && _controller != null) {
      return _controller!;
    }

    _controller = WhisperController();
    _isInitialized = true;
    return _controller!;
  }

  @override
  Future<TranscriptionResult> transcribe(
    String audioPath, {
    String language = 'ko',
  }) async {
    final stopwatch = Stopwatch()..start();

    try {
      final controller = await _getController();

      // 모델 파일이 없으면 최초 전사 시점에 다운로드합니다.
      if (!await _isModelLoaded(controller, _model)) {
        await controller.downloadModel(_model);
      }

      final result = await controller.transcribe(
        model: _model,
        audioPath: audioPath,
        lang: language,
        withTimestamps: true,
      );

      if (result == null) {
        throw const SttException('Transcription returned null');
      }

      stopwatch.stop();
      return TranscriptionResult(
        text: result.transcription.text,
        segments: result.transcription.segments
                ?.map(
                  (segment) => TranscriptionSegment(
                    startTime: segment.fromTs,
                    endTime: segment.toTs,
                    text: segment.text,
                  ),
                )
                .toList() ??
            const [],
        language: language,
        // OfflineSttService wrapper에서 오프라인 여부를 최종 조정합니다.
        offline: false,
        createdAt: DateTime.now(),
        processingDuration: stopwatch.elapsed,
        engineInfo: 'whisper-base-ggml',
      );
    } on SttException {
      rethrow;
    } on Exception catch (e) {
      throw SttException('Transcription failed: ${e.toString()}');
    }
  }

  @override
  Future<bool> isAvailable() async {
    try {
      final controller = await _getController();
      return _isModelLoaded(controller, _model);
    } on Exception {
      return false;
    }
  }

  @override
  Future<EngineInfo> getEngineInfo() async {
    return EngineInfo(
      name: 'whisper_ggml_plus',
      platform: _getPlatformName(),
      modelVersion: 'whisper-base',
      accelerator: 'auto',
    );
  }

  @override
  Stream<double> get progressStream => const Stream.empty();

  /// 네이티브 리소스를 해제합니다.
  Future<void> dispose() async {
    await _controller?.dispose(model: _model);
    _controller = null;
    _isInitialized = false;
  }

  Future<bool> _isModelLoaded(
    WhisperController controller,
    WhisperModel model,
  ) async {
    final path = await controller.getPath(model);
    return File(path).existsSync();
  }

  String _getPlatformName() {
    if (kIsWeb) return 'web';
    if (Platform.isIOS) return 'ios';
    if (Platform.isAndroid) return 'android';
    if (Platform.isMacOS) return 'macos';
    if (Platform.isWindows) return 'windows';
    if (Platform.isLinux) return 'linux';
    return 'unknown';
  }
}
