// SPEC-TONE-001: 톤 타임라인 위젯 (REQ-TONE-012, REQ-TONE-013)
// @MX:SPEC: SPEC-TONE-001
// 패턴 매칭: result_screen.dart::_SentimentContent (Card 기반 레이아웃, Material 내장 위젯)
//
// @MX:ANCHOR: ToneSection은 _SentimentContent ListView 하단에 배치됨
// @MX:REASON: 별도 ConsumerWidget으로 toneProvider를 독립 watch → 오류 격리 (REQ-TONE-013)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/tone_model.dart';
import 'package:voice_to_textnote/providers/result_provider.dart';
import 'package:voice_to_textnote/services/tone_api.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';
import 'package:voice_to_textnote/widgets/error_retry_widget.dart';

/// 톤 클래스 → 색상 매핑 (REQ-TONE-012 색상 계약)
///
/// @MX:NOTE: 백엔드 톤 레이블과 클라이언트 색상의 1:1 계약
/// calm=indigo, excited=amber, authoritative=violet, hesitant=orange,
/// monotone=neutral, unknown=muted
Color toneColor(String tone) {
  switch (tone) {
    case 'calm':
      return AppColors.indigo500;
    case 'excited':
      return AppColors.warning;
    case 'authoritative':
      return AppColors.violet500;
    case 'hesitant':
      return const Color(0xFFF97316); // orange-500
    case 'monotone':
      return const Color(0xFF9CA3AF);
    case 'unknown':
    default:
      return AppColors.lightTextTertiary;
  }
}

/// 톤 타임라인 카드 - 세그먼트별 색상 막대 + 화자 + 톤 + 신뢰도
///
/// REQ-TONE-012: tone 데이터가 있을 때 타임라인 렌더링
/// Material 내장 위젯만 사용 (외부 차트 라이브러리 금지)
class ToneTimeline extends StatelessWidget {
  final ToneResponse response;

  const ToneTimeline({super.key, required this.response});

  String _formatTime(double seconds) {
    final m = (seconds / 60).floor();
    final s = (seconds % 60).round();
    return m > 0 ? '$m:${s.toString().padLeft(2, '0')}' : '${s}s';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.graphic_eq,
                    size: 20, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text('톤 타임라인', style: theme.textTheme.titleMedium),
              ],
            ),
            const SizedBox(height: 12),
            if (response.segments.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  '세그먼트가 없습니다',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.outline,
                  ),
                ),
              )
            else
              ...response.segments.map((seg) => _buildSegmentRow(theme, seg)),
          ],
        ),
      ),
    );
  }

  Widget _buildSegmentRow(ThemeData theme, ToneSegment seg) {
    final color = toneColor(seg.tone);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          // 시간 범위
          SizedBox(
            width: 100,
            child: Text(
              '${_formatTime(seg.start)} - ${_formatTime(seg.end)}',
              style: theme.textTheme.bodySmall?.copyWith(
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
          // 색상 막대
          Container(width: 4, height: 28, color: color),
          const SizedBox(width: 8),
          // 화자 + 톤 + 신뢰도
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  seg.speaker,
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 13),
                ),
                Text(
                  '${seg.tone} · ${(seg.confidence * 100).toStringAsFixed(0)}%',
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
          ),
          // 톤 라벨 칩
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: color.withAlpha(40),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: color.withAlpha(80)),
            ),
            child: Text(
              seg.tone,
              style: TextStyle(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 화자별 톤 요약 카드 - SpeakerTone 리스트 렌더링
class _SpeakerToneSummary extends StatelessWidget {
  final List<SpeakerTone> speakers;

  const _SpeakerToneSummary({required this.speakers});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('화자별 톤 요약', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            ...speakers.map((s) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      Container(
                        width: 12,
                        height: 12,
                        decoration: BoxDecoration(
                          color: toneColor(s.dominantTone),
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          s.speaker,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ),
                      Text(
                        '주요 톤: ${s.dominantTone}',
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }
}

/// 톤 분석 섹션 - Riverpod 기반 독립 오류 격리
///
/// REQ-TONE-012: 로딩 → ProgressIndicator, 빈 데이터 → EmptyStateWidget
/// REQ-TONE-013: 오류 → ErrorRetryWidget (SizedBox.shrink 금지)
///               toneProvider 실패 시 상위 sentiment 위젯에 영향 없음 (별도 watch)
class ToneSection extends ConsumerWidget {
  final String meetingId;

  const ToneSection({super.key, required this.meetingId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final toneAsync = ref.watch(toneProvider(meetingId));

    return toneAsync.when(
      loading: () => const SizedBox(
        height: 120,
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (error, _) {
        if (error is ToneDisabledException || error is ToneNotFoundException) {
          return const EmptyStateWidget(
            icon: Icons.graphic_eq_outlined,
            title: '톤 분석 데이터가 없습니다',
            subtitle: '음성 톤 분석이 완료된 후 확인할 수 있습니다',
          );
        }
        return ErrorRetryWidget(
          message: '톤 분석을 불러올 수 없습니다',
          onRetry: () => ref.invalidate(toneProvider(meetingId)),
        );
      },
      data: (response) {
        // REQ-TONE-012: 빈 데이터 → EmptyStateWidget
        if (response.segments.isEmpty && response.speakers.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.graphic_eq_outlined,
            title: '톤 분석 데이터가 없습니다',
            subtitle: '음성 톤 분석이 완료된 후 확인할 수 있습니다',
          );
        }
        // REQ-TONE-012: 정상 데이터 → 화자 요약 + 타임라인
        return Column(
          children: [
            if (response.speakers.isNotEmpty)
              _SpeakerToneSummary(speakers: response.speakers),
            ToneTimeline(response: response),
          ],
        );
      },
    );
  }
}
