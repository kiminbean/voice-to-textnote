// 미니 오디오 플레이어 바 - 재생/일시정지, 진행 바, 시간 표시, 속도 제어
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/providers/audio_player_provider.dart';

const _speedOptions = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

class AudioPlayerBar extends ConsumerStatefulWidget {
  final String taskId;

  const AudioPlayerBar({super.key, required this.taskId});

  @override
  ConsumerState<AudioPlayerBar> createState() => _AudioPlayerBarState();
}

class _AudioPlayerBarState extends ConsumerState<AudioPlayerBar> {
  @override
  Widget build(BuildContext context) {
    final audioState = ref.watch(audioPlayerProvider);
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              _buildPlayButton(audioState, theme),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _buildProgressBar(audioState, theme),
                    const SizedBox(height: 4),
                    _buildTimeLabels(audioState, theme),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          _buildSpeedChips(audioState, theme),
          if (audioState.errorMessage != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                '오디오를 재생할 수 없습니다',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildSpeedChips(AudioState audioState, ThemeData theme) {
    return SizedBox(
      height: 28,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _speedOptions.length,
        separatorBuilder: (_, __) => const SizedBox(width: 4),
        itemBuilder: (_, index) {
          final speed = _speedOptions[index];
          final isSelected = (audioState.speed - speed).abs() < 0.01;
          return ChoiceChip(
            label: Text(
              speed == speed.roundToDouble()
                  ? '${speed.toInt()}x'
                  : '${speed}x',
              style: TextStyle(
                fontSize: 11,
                color: isSelected
                    ? theme.colorScheme.onPrimary
                    : theme.colorScheme.onSurface,
              ),
            ),
            selected: isSelected,
            showCheckmark: false,
            visualDensity: VisualDensity.compact,
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            onSelected: (_) {
              ref.read(audioPlayerProvider.notifier).setSpeed(speed);
            },
          );
        },
      ),
    );
  }

  Widget _buildPlayButton(AudioState audioState, ThemeData theme) {
    final isLoading = audioState.playbackState == AudioPlaybackState.loading;
    final isPlaying = audioState.playbackState == AudioPlaybackState.playing;

    return IconButton.filled(
      icon: isLoading
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: Colors.white,
              ),
            )
          : Icon(isPlaying ? Icons.pause : Icons.play_arrow),
      onPressed: isLoading ? null : () => _onPlayPause(audioState),
      iconSize: 28,
    );
  }

  Widget _buildProgressBar(AudioState audioState, ThemeData theme) {
    final duration = audioState.duration.inMilliseconds.toDouble();
    final position = audioState.position.inMilliseconds.toDouble();
    final value = duration > 0 ? (position / duration).clamp(0.0, 1.0) : 0.0;

    return SliderTheme(
      data: SliderThemeData(
        trackHeight: 3,
        thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
        overlayShape: const RoundSliderOverlayShape(overlayRadius: 12),
        activeTrackColor: theme.colorScheme.primary,
        inactiveTrackColor: theme.colorScheme.outlineVariant,
        thumbColor: theme.colorScheme.primary,
      ),
      child: Slider(
        value: value,
        onChanged: (v) {
          if (duration > 0) {
            final seekPos = Duration(milliseconds: (v * duration).round());
            ref.read(audioPlayerProvider.notifier).seekTo(seekPos);
          }
        },
      ),
    );
  }

  Widget _buildTimeLabels(AudioState audioState, ThemeData theme) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          _formatDuration(audioState.position),
          style: theme.textTheme.labelSmall,
        ),
        Text(
          _formatDuration(audioState.duration),
          style: theme.textTheme.labelSmall,
        ),
      ],
    );
  }

  Future<void> _onPlayPause(AudioState audioState) async {
    final notifier = ref.read(audioPlayerProvider.notifier);
    switch (audioState.playbackState) {
      case AudioPlaybackState.stopped:
      case AudioPlaybackState.error:
        await notifier.play(widget.taskId);
      case AudioPlaybackState.playing:
        await notifier.pause();
      case AudioPlaybackState.paused:
        await notifier.resume();
      case AudioPlaybackState.loading:
        break;
    }
  }

  String _formatDuration(Duration d) {
    final h = d.inHours;
    final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return h > 0 ? '$h:$m:$s' : '$m:$s';
  }
}
