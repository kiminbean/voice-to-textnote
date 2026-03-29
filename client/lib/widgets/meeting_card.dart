// 미팅 목록 카드 위젯
// @MX:NOTE: SPEC-HISTSYNC-001 REQ-HSYNC-005 - onLongPress 삭제 콜백 추가
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:voice_to_textnote/models/meeting.dart';

class MeetingCard extends StatelessWidget {
  final Meeting meeting;
  final VoidCallback? onTap;
  // REQ-HSYNC-005: 롱프레스 삭제 콜백
  final VoidCallback? onLongPress;

  const MeetingCard({
    super.key,
    required this.meeting,
    this.onTap,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListTile(
        onTap: onTap,
        onLongPress: onLongPress,
        title: Text(
          meeting.title,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        subtitle: Text(
          DateFormat('yyyy년 MM월 dd일 HH:mm').format(meeting.createdAt),
          style: Theme.of(context).textTheme.bodySmall,
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 소요 시간 표시
            if (meeting.duration != null)
              Text(
                _formatDuration(meeting.duration!),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            const SizedBox(width: 8),
            // 상태 배지
            _buildStatusBadge(context, meeting.status),
          ],
        ),
      ),
    );
  }

  // 상태 배지 생성
  Widget _buildStatusBadge(BuildContext context, MeetingStatus status) {
    final (label, color) = switch (status) {
      MeetingStatus.recording => ('녹음 중', Colors.red),
      MeetingStatus.processing => ('처리 중', Colors.orange),
      MeetingStatus.completed => ('완료', Colors.green),
      MeetingStatus.failed => ('실패', Colors.grey),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withAlpha(30),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  // Duration을 읽기 쉬운 형식으로 변환
  String _formatDuration(Duration duration) {
    final minutes = duration.inMinutes;
    final seconds = duration.inSeconds % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}';
  }
}
