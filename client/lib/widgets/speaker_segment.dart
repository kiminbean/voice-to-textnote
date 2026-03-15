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

  const SpeakerSegment({
    super.key,
    required this.speakerName,
    required this.text,
    this.startTime,
    this.speakerIndex = 0,
  });

  @override
  Widget build(BuildContext context) {
    final color = _speakerColors[speakerIndex % _speakerColors.length];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 화자 이름 (컬러로 구분)
          SizedBox(
            width: 80,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  speakerName,
                  style: TextStyle(
                    color: color,
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
                // 타임스탬프 표시
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
          const SizedBox(width: 8),
          // 발화 텍스트
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: color.withAlpha(15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: color.withAlpha(50)),
              ),
              child: Text(
                text,
                style: const TextStyle(fontSize: 14, height: 1.5),
              ),
            ),
          ),
        ],
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
