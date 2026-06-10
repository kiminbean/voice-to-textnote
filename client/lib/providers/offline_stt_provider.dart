import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/foundation.dart';
import 'package:voice_to_textnote/models/transcription_result.dart';
import 'package:voice_to_textnote/services/offline_stt_service.dart';
import 'package:voice_to_textnote/services/platform_stt_service.dart';

/// @MX:SPEC:REQ-MOBILE-008
///
/// 오프라인 STT 상태 관리 Provider
///
/// offline, preprocessing, transcribing, completed, failed 상태를 관리하며
/// 진행률 Stream을 UI에 노출합니다.
class OfflineSttNotifier extends StateNotifier<OfflineSttState> {
  final OfflineSttService _service;

  OfflineSttNotifier(this._service) : super(const OfflineSttState.idle());

  /// WAV 파일을 오프라인 STT로 변환
  ///
  /// [wavPath] 변환할 WAV 파일 경로
  Future<void> transcribe(String wavPath) async {
    state = const OfflineSttState.preprocessing(progress: 0.0);

    try {
      final progressStream = _service.transcribeWithProgress(wavPath);

      await for (final progress in progressStream) {
        state = OfflineSttState.transcribing(
          progress: progress.progress,
          result: progress.result,
          status: _mapStatus(progress.status),
          error: progress.error,
        );
      }

      // 완료 상태로 전환
      final currentState = state;
      if (currentState.result != null) {
        state = OfflineSttState.completed(
          result: currentState.result!,
          progress: 100.0,
        );
      }
    } catch (e) {
      state = OfflineSttState.failed(
        error: e.toString(),
        progress: state.progress,
      );
    }
  }

  /// TranscriptionStatus를 OfflineSttStatus로 매핑
  OfflineSttStatus _mapStatus(TranscriptionStatus status) {
    switch (status) {
      case TranscriptionStatus.starting:
      case TranscriptionStatus.processing:
        return OfflineSttStatus.processing;
      case TranscriptionStatus.completed:
        return OfflineSttStatus.completed;
      case TranscriptionStatus.failed:
        return OfflineSttStatus.failed;
    }
  }

  /// 현재 진행률 Stream
  Stream<double> get progressStream => stream.map((s) => s.progress);
}

/// 오프라인 STT 상태
@immutable
sealed class OfflineSttState {
  const OfflineSttState();

  /// 진행률
  double get progress => 0.0;

  /// 현재 상태
  OfflineSttStatus get status => OfflineSttStatus.idle;

  /// 변환 결과 (완료 시에만 설정)
  TranscriptionResult? get result => null;

  /// 에러 메시지 (실패 시에만 설정)
  String? get error => null;

  /// IDLE 상태
  const factory OfflineSttState.idle() = OfflineSttStateIdle._;

  /// 전처리 중 상태
  const factory OfflineSttState.preprocessing({required double progress}) =
      OfflineSttStatePreprocessing;

  /// 변환 중 상태
  const factory OfflineSttState.transcribing({
    required double progress,
    TranscriptionResult? result,
    required OfflineSttStatus status,
    String? error,
  }) = OfflineSttStateTranscribing;

  /// 완료 상태
  const factory OfflineSttState.completed({
    required TranscriptionResult result,
    required double progress,
  }) = OfflineSttStateCompleted;

  /// 실패 상태
  const factory OfflineSttState.failed({
    required String error,
    required double progress,
  }) = OfflineSttStateFailed;
}

/// IDLE 상태
class OfflineSttStateIdle extends OfflineSttState {
  const OfflineSttStateIdle._();
}

/// 전처리 중 상태
class OfflineSttStatePreprocessing extends OfflineSttState {
  @override
  final double progress;

  const OfflineSttStatePreprocessing({required this.progress});
}

/// 변환 중 상태
class OfflineSttStateTranscribing extends OfflineSttState {
  @override
  final double progress;

  @override
  final TranscriptionResult? result;

  @override
  final OfflineSttStatus status;

  @override
  final String? error;

  const OfflineSttStateTranscribing({
    required this.progress,
    this.result,
    required this.status,
    this.error,
  });
}

/// 완료 상태
class OfflineSttStateCompleted extends OfflineSttState {
  @override
  final double progress;

  @override
  final TranscriptionResult result;

  @override
  final OfflineSttStatus status = OfflineSttStatus.completed;

  @override
  final String? error;

  const OfflineSttStateCompleted({
    required this.progress,
    required this.result,
  }) : error = null;
}

/// 실패 상태
class OfflineSttStateFailed extends OfflineSttState {
  @override
  final double progress;

  @override
  final TranscriptionResult? result;

  @override
  final OfflineSttStatus status = OfflineSttStatus.failed;

  @override
  final String? error;

  const OfflineSttStateFailed({
    required this.error,
    required this.progress,
  }) : result = null;
}

/// 오프라인 STT 상태
enum OfflineSttStatus {
  /// 대기 중
  idle,

  /// 처리 중
  processing,

  /// 완료
  completed,

  /// 실패
  failed,
}

/// @MX:NOTE: 오프라인 STT Provider
///
/// 오프라인 STT 기능을 위한 Riverpod Provider
///
/// 사용법:
/// ```dart
/// final offlineSttProvider = StateNotifierProvider<OfflineSttNotifier, OfflineSttState>(
///   (ref) {
///     final service = ref.watch(platformSttServiceProvider);
///     return OfflineSttNotifier(service);
///   },
/// );
/// ```
final platformSttServiceProvider = Provider<PlatformSttService>((ref) {
  return PlatformSttServiceImpl();
});

final offlineSttServiceProvider = Provider<OfflineSttService>((ref) {
  return OfflineSttService(ref.watch(platformSttServiceProvider));
});

final offlineSttProvider =
    StateNotifierProvider<OfflineSttNotifier, OfflineSttState>((ref) {
  return OfflineSttNotifier(ref.watch(offlineSttServiceProvider));
});
