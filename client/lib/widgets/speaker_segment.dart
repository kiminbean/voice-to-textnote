// 화자 발화 세그먼트 위젯
import 'package:flutter/material.dart';

// 화자별 색상 목록 (최대 10명)
const _speakerColors = [
  Colors.blue,
  Colors.green,
  Colors.orange,
  Colors.purple,
  Colors.red,
  Colors.teal,
  Colors.indigo,
  Colors.pink,
  Colors.brown,
  Colors.cyan,
];

class SpeakerSegment extends StatelessWidget {
  final String speakerName;
  final String text;
  final Duration? startTime;
  final int speakerIndex;
  final String? searchQuery;
  final bool isHighlighted;
  final VoidCallback? onSpeakerTap;

  const SpeakerSegment({
    super.key,
    required this.speakerName,
    required this.text,
    this.startTime,
    this.speakerIndex = 0,
    this.searchQuery,
    this.isHighlighted = false,
    this.onSpeakerTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = _speakerColors[speakerIndex % _speakerColors.length];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ConstrainedBox(
            constraints: const BoxConstraints(minWidth: 60, maxWidth: 90),
            child: GestureDetector(
              onTap: onSpeakerTap,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    speakerName,
                    style: TextStyle(
                      color: color,
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                      decoration: onSpeakerTap != null
                          ? TextDecoration.underline
                          : null,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (startTime != null)
                    Text(
                      _formatTime(startTime!),
                      style: TextStyle(
                        color: Colors.grey[500],
                        fontSize: 11,
                      ),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isHighlighted
                    ? color.withAlpha(40)
                    : color.withAlpha(15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: isHighlighted ? color : color.withAlpha(50),
                  width: isHighlighted ? 2 : 1,
                ),
              ),
              child: _buildHighlightedText(context),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHighlightedText(BuildContext context) {
    if (searchQuery == null || searchQuery!.isEmpty) {
      return Text(
        text,
        style: const TextStyle(fontSize: 14, height: 1.5),
      );
    }

    final matches = RegExp(RegExp.escape(searchQuery!), caseSensitive: false).allMatches(text).toList();
    if (matches.isEmpty) {
      return Text(
        text,
        style: const TextStyle(fontSize: 14, height: 1.5),
      );
    }

    final spans = <TextSpan>[];
    int lastMatchEnd = 0;

    for (final match in matches) {
      if (match.start > lastMatchEnd) {
        spans.add(TextSpan(text: text.substring(lastMatchEnd, match.start)));
      }
      spans.add(TextSpan(
        text: text.substring(match.start, match.end),
        style: const TextStyle(backgroundColor: Colors.yellow, color: Colors.black),
      ));
      lastMatchEnd = match.end;
    }

    if (lastMatchEnd < text.length) {
      spans.add(TextSpan(text: text.substring(lastMatchEnd)));
    }

    return RichText(
      text: TextSpan(
        style: DefaultTextStyle.of(context).style.copyWith(fontSize: 14, height: 1.5),
        children: spans,
      ),
    );
  }

  // Duration을 타임스탬프 형식으로 변환
  String _formatTime(Duration duration) {
    final minutes = duration.inMinutes;
    final seconds = duration.inSeconds % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}';
  }
}
