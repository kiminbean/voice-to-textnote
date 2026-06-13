// 오디오 재생 상태 관리 - just_audio 기반
import 'package:just_audio/just_audio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/audio_api.dart';

/// 재생 상태
enum AudioPlaybackState { stopped, playing, paused, loading, error }

/// 오디오 플레이어 상태
class AudioState {
  final AudioPlaybackState playbackState;
  final Duration position;
  final Duration duration;
  final double speed;
  final String? errorMessage;

  const AudioState({
    this.playbackState = AudioPlaybackState.stopped,
    this.position = Duration.zero,
    this.duration = Duration.zero,
    this.speed = 1.0,
    this.errorMessage,
  });

  AudioState copyWith({
    AudioPlaybackState? playbackState,
    Duration? position,
    Duration? duration,
    double? speed,
    String? errorMessage,
  }) {
    return AudioState(
      playbackState: playbackState ?? this.playbackState,
      position: position ?? this.position,
      duration: duration ?? this.duration,
      speed: speed ?? this.speed,
      errorMessage: errorMessage,
    );
  }
}

class AudioPlayerNotifier extends StateNotifier<AudioState> {
  final AudioPlayer _player;
  final AudioApi _audioApi;

  AudioPlayerNotifier(this._audioApi)
      : _player = AudioPlayer(),
        super(const AudioState()) {
    _listenToPlayer();
  }

  void _listenToPlayer() {
    _player.positionStream.listen((pos) {
      if (state.playbackState != AudioPlaybackState.error) {
        state = state.copyWith(position: pos);
      }
    });

    _player.durationStream.listen((dur) {
      if (dur != null) {
        state = state.copyWith(duration: dur);
      }
    });

    _player.playerStateStream.listen((ps) {
      final playback = switch (ps.processingState) {
        ProcessingState.loading => AudioPlaybackState.loading,
        ProcessingState.buffering => AudioPlaybackState.loading,
        ProcessingState.completed => AudioPlaybackState.stopped,
        ProcessingState.idle =>
          ps.playing ? AudioPlaybackState.loading : AudioPlaybackState.stopped,
        ProcessingState.ready =>
          ps.playing ? AudioPlaybackState.playing : AudioPlaybackState.paused,
      };
      state = state.copyWith(playbackState: playback);
    });
  }

  /// 오디오 로드 및 재생
  Future<void> play(String taskId) async {
    try {
      state = state.copyWith(playbackState: AudioPlaybackState.loading);
      final url = _audioApi.getAudioUrl(taskId);
      await _player.setUrl(url);
      await _player.play();
    } catch (e) {
      state = state.copyWith(
        playbackState: AudioPlaybackState.error,
        errorMessage: e.toString(),
      );
    }
  }

  Future<void> pause() async => _player.pause();

  Future<void> resume() async => _player.play();

  Future<void> stop() async {
    await _player.stop();
    state = const AudioState();
  }

  Future<void> seekTo(Duration pos) async => _player.seek(pos);

  Future<void> setSpeed(double rate) async {
    await _player.setSpeed(rate);
    state = state.copyWith(speed: rate);
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }
}

final audioPlayerProvider =
    StateNotifierProvider<AudioPlayerNotifier, AudioState>((ref) {
  final audioApi = ref.watch(audioApiProvider);
  return AudioPlayerNotifier(audioApi);
});
