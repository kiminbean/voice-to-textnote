import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/audio_enhancement_api.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';

class AudioEnhancementPanel extends ConsumerStatefulWidget {
  final String audioFilePath;

  const AudioEnhancementPanel({
    super.key,
    required this.audioFilePath,
  });

  @override
  ConsumerState<AudioEnhancementPanel> createState() =>
      _AudioEnhancementPanelState();
}

class AudioEnhancementLauncher extends StatelessWidget {
  final String audioFilePath;

  const AudioEnhancementLauncher({
    super.key,
    required this.audioFilePath,
  });

  Future<void> _showPanel(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) {
        return Padding(
          padding: EdgeInsets.only(
            left: AppSpacing.md,
            right: AppSpacing.md,
            top: AppSpacing.sm,
            bottom:
                MediaQuery.of(sheetContext).viewInsets.bottom + AppSpacing.md,
          ),
          child: SingleChildScrollView(
            child: AudioEnhancementPanel(audioFilePath: audioFilePath),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: () => _showPanel(context),
        icon: const Icon(Icons.auto_fix_high_rounded),
        label: const Text('오디오 향상'),
      ),
    );
  }
}

class _AudioEnhancementPanelState extends ConsumerState<AudioEnhancementPanel> {
  EnhancementMode _mode = EnhancementMode.enhanced;
  NoiseReductionLevel _noiseLevel = NoiseReductionLevel.moderate;
  VoiceEnhancementMode _voiceMode = VoiceEnhancementMode.natural;
  bool _extractSpeechOnly = false;
  bool _normalizeAudio = true;
  bool _isProcessing = false;
  AudioEnhancementResult? _result;
  String? _errorMessage;

  Future<void> _runEnhancement() async {
    if (_isProcessing) return;

    setState(() {
      _isProcessing = true;
      _errorMessage = null;
    });

    try {
      final api = ref.read(audioEnhancementApiProvider);
      final response = await api.enhance(
        widget.audioFilePath,
        options: AudioEnhancementOptions(
          enhancementMode: _mode,
          noiseReductionLevel: _noiseLevel,
          voiceEnhancement: _voiceMode,
          extractSpeechOnly: _extractSpeechOnly,
          normalizeAudio: _normalizeAudio,
        ),
      );

      if (!mounted) return;
      setState(() => _result = response.result);

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('오디오 향상이 완료되었습니다')),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _errorMessage = e.toString());
    } finally {
      if (mounted) {
        setState(() => _isProcessing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.graphic_eq_rounded, size: 20),
                const SizedBox(width: AppSpacing.sm),
                Text('오디오 향상', style: theme.textTheme.titleMedium),
                const Spacer(),
                IconButton(
                  tooltip: '실행',
                  onPressed: _isProcessing ? null : _runEnhancement,
                  icon: _isProcessing
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.auto_fix_high_rounded),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                _ChoiceMenu<EnhancementMode>(
                  tooltip: '향상 모드',
                  icon: Icons.tune_rounded,
                  value: _mode,
                  values: EnhancementMode.values,
                  labelFor: _modeLabel,
                  onSelected: (value) => setState(() => _mode = value),
                ),
                _ChoiceMenu<NoiseReductionLevel>(
                  tooltip: '노이즈 감소',
                  icon: Icons.noise_control_off_rounded,
                  value: _noiseLevel,
                  values: NoiseReductionLevel.values,
                  labelFor: _noiseLabel,
                  onSelected: (value) => setState(() => _noiseLevel = value),
                ),
                _ChoiceMenu<VoiceEnhancementMode>(
                  tooltip: '보이스',
                  icon: Icons.record_voice_over_rounded,
                  value: _voiceMode,
                  values: VoiceEnhancementMode.values,
                  labelFor: _voiceLabel,
                  onSelected: (value) => setState(() => _voiceMode = value),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: [
                Expanded(
                  child: CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    value: _extractSpeechOnly,
                    onChanged: (value) =>
                        setState(() => _extractSpeechOnly = value ?? false),
                    title: const Text('음성만'),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                ),
                Expanded(
                  child: CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    value: _normalizeAudio,
                    onChanged: (value) =>
                        setState(() => _normalizeAudio = value ?? true),
                    title: const Text('정규화'),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                ),
              ],
            ),
            if (_errorMessage != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                _errorMessage!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ],
            if (_result != null) ...[
              const Divider(height: AppSpacing.lg),
              _QualitySummary(result: _result!),
            ],
          ],
        ),
      ),
    );
  }
}

class _ChoiceMenu<T> extends StatelessWidget {
  final String tooltip;
  final IconData icon;
  final T value;
  final List<T> values;
  final String Function(T) labelFor;
  final ValueChanged<T> onSelected;

  const _ChoiceMenu({
    required this.tooltip,
    required this.icon,
    required this.value,
    required this.values,
    required this.labelFor,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return MenuAnchor(
      builder: (context, controller, child) {
        return Tooltip(
          message: tooltip,
          child: OutlinedButton.icon(
            onPressed: () =>
                controller.isOpen ? controller.close() : controller.open(),
            icon: Icon(icon, size: 18),
            label: Text(labelFor(value)),
          ),
        );
      },
      menuChildren: values
          .map(
            (item) => MenuItemButton(
              onPressed: () => onSelected(item),
              child: Text(labelFor(item)),
            ),
          )
          .toList(),
    );
  }
}

class _QualitySummary extends StatelessWidget {
  final AudioEnhancementResult result;

  const _QualitySummary({required this.result});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _ScoreRow(label: '전체', value: result.qualityScores.overallScore),
        _ScoreRow(label: '명확도', value: result.qualityScores.clarityScore),
        _ScoreRow(label: '음성', value: result.qualityScores.voiceActivityRatio),
        if (result.warnings.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.sm),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                result.warnings.join('\n'),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
      ],
    );
  }
}

class _ScoreRow extends StatelessWidget {
  final String label;
  final double value;

  const _ScoreRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(width: 56, child: Text(label)),
          Expanded(child: LinearProgressIndicator(value: value)),
          const SizedBox(width: AppSpacing.sm),
          SizedBox(
            width: 44,
            child: Text(
              '${(value * 100).round()}%',
              textAlign: TextAlign.end,
            ),
          ),
        ],
      ),
    );
  }
}

String _modeLabel(EnhancementMode mode) => switch (mode) {
      EnhancementMode.clean => '클린',
      EnhancementMode.enhanced => '향상',
      EnhancementMode.speechOnly => '음성',
      EnhancementMode.musicFocused => '음악',
    };

String _noiseLabel(NoiseReductionLevel level) => switch (level) {
      NoiseReductionLevel.light => '약함',
      NoiseReductionLevel.moderate => '중간',
      NoiseReductionLevel.aggressive => '강함',
    };

String _voiceLabel(VoiceEnhancementMode mode) => switch (mode) {
      VoiceEnhancementMode.natural => '자연',
      VoiceEnhancementMode.clear => '명료',
      VoiceEnhancementMode.broadcast => '방송',
    };
