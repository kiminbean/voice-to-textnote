// 녹음 품질 선택 위젯
// @MX:NOTE: SPEC-APP-005 REQ-003,004,005 — 녹음 품질 프리셋 선택 및 현재 설정 표시

import 'package:flutter/material.dart';
import 'package:voice_to_textnote/models/recording_config.dart';

/// 녹음 품질 선택 위젯
class RecordingQualitySelector extends StatelessWidget {
  /// 현재 선택된 품질 설정
  final RecordingConfig currentConfig;

  /// 품질 변경 콜백
  final ValueChanged<RecordingConfig> onChanged;

  /// 녹음 중 여부 (true면 비활성화)
  final bool isRecording;

  const RecordingQualitySelector({
    super.key,
    required this.currentConfig,
    required this.onChanged,
    this.isRecording = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // 현재 설정 표시 (REQ-005)
        Text(
          '현재 설정: ${currentConfig.summary}',
          style: TextStyle(
            fontSize: 13,
            color: isRecording
                ? Theme.of(context).disabledColor
                : Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 8),
        // 품질 선택 칩 (REQ-003)
        Wrap(
          spacing: 8,
          children: RecordingConfig.presets.map((preset) {
            final isSelected = preset == currentConfig;
            return ChoiceChip(
              label: Text(preset.label),
              selected: isSelected,
              onSelected: isRecording ? null : (_) => onChanged(preset),
              disabledColor: Theme.of(context).disabledColor.withAlpha(30),
            );
          }).toList(),
        ),
        // 녹음 중 잠금 안내 (REQ-004)
        if (isRecording)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.lock_outline, size: 14, color: Theme.of(context).disabledColor),
                const SizedBox(width: 4),
                Text(
                  '녹음 중에는 변경할 수 없습니다',
                  style: TextStyle(
                    fontSize: 11,
                    color: Theme.of(context).disabledColor,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
