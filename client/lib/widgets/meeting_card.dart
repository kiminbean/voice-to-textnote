// 미팅 목록 카드 위젯 — 모던 미니멀
// @MX:NOTE: SPEC-HISTSYNC-001 REQ-HSYNC-005 - onLongPress 삭제 콜백 유지
// @MX:WARN: Hero tag 'meeting-${id}' 는 result_screen 전환 애니메이션과 쌍을 이룸 — 변경 시 양쪽 수정.
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';
import 'package:voice_to_textnote/widgets/status_badge.dart';

class MeetingCard extends StatelessWidget {
  final Meeting meeting;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  const MeetingCard({
    super.key,
    required this.meeting,
    this.onTap,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);

    return Hero(
      tag: 'meeting-${meeting.id}',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          onLongPress: onLongPress,
          borderRadius: AppRadius.brLg,
          child: Container(
            padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.lg, vertical: AppSpacing.md + 2),
            decoration: BoxDecoration(
              color: scheme.surface,
              borderRadius: AppRadius.brLg,
              border: Border.all(color: scheme.border),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                // 좌측: 제목 + 메타
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        meeting.title,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              color: scheme.textPrimary,
                            ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          Icon(Icons.schedule_outlined,
                              size: 14, color: scheme.textTertiary),
                          const SizedBox(width: 4),
                          Flexible(
                            child: Text(
                              DateFormat('yyyy. MM. dd. HH:mm')
                                  .format(meeting.createdAt),
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: scheme.textTertiary,
                                  ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                // 우측: 소요시간 + 상태
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    if (meeting.duration != null)
                      Text(
                        _formatDuration(meeting.duration!),
                        style: TextStyle(
                          fontFeatures: const [FontFeature.tabularFigures()],
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: scheme.textSecondary,
                        ),
                      ),
                    const SizedBox(height: 6),
                    StatusBadge.auto(label: _statusLabel(meeting.status), dot: true),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _statusLabel(MeetingStatus status) => switch (status) {
        MeetingStatus.recording => '녹음 중',
        MeetingStatus.processing => '처리 중',
        MeetingStatus.completed => '완료',
        MeetingStatus.failed => '실패',
      };

  String _formatDuration(Duration duration) {
    final minutes = duration.inMinutes;
    final seconds = duration.inSeconds % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}';
  }
}
