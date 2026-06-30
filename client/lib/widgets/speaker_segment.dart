// 화자 발화 세그먼트 위젯 — 모던 팔레트
import 'package:flutter/material.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';

// 화자별 색상 팔레트 (최대 10명) — 명확히 구분되는 모던 색상
const _speakerColors = [
  AppColors.indigo600, // 1번 화자 — 브랜드 인디고
  AppColors.success, // 2번 — 에메랄드
  AppColors.warning, // 3번 — 앰버
  AppColors.violet500, // 4번 — 바이올렛
  AppColors.error, // 5번 — 레드/로즈
  Color(0xFF0D9488), // 6번 — 틸
  Color(0xFF2563EB), // 7번 — 블루
  Color(0xFFEC4899), // 8번 — 핑크
  Color(0xFFEA580C), // 9번 — 오렌지
  Color(0xFF0891B2), // 10번 — 시안
];

class SpeakerSegment extends StatelessWidget {
  final String speakerName;
  final String text;
  final Duration? startTime;
  final Duration? endTime;
  final int speakerIndex;
  final bool isEstimatedSpeaker;
  final double? voiceprintSimilarity;
  final String? searchQuery;
  final bool isHighlighted;
  final VoidCallback? onSpeakerTap;

  const SpeakerSegment({
    super.key,
    required this.speakerName,
    required this.text,
    this.startTime,
    this.endTime,
    this.speakerIndex = 0,
    this.isEstimatedSpeaker = false,
    this.voiceprintSimilarity,
    this.searchQuery,
    this.isHighlighted = false,
    this.onSpeakerTap,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    final color = _speakerColors[speakerIndex % _speakerColors.length];

    return Padding(
      padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ConstrainedBox(
            constraints: const BoxConstraints(minWidth: 64, maxWidth: 96),
            child: GestureDetector(
              onTap: onSpeakerTap,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: color.withAlpha(scheme.isDark ? 40 : 20),
                      borderRadius: AppRadius.brSm,
                    ),
                    child: Text(
                      speakerName,
                      style: TextStyle(
                        color: color,
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  if (isEstimatedSpeaker) ...[
                    const SizedBox(height: 4),
                    Tooltip(
                      message: voiceprintSimilarity == null
                          ? '목소리 기반 자동 추정입니다. 맞으면 이름을 눌러 저장하고, 틀리면 수정하세요.'
                          : '목소리 유사도 ${(voiceprintSimilarity! * 100).round()}% 자동 추정입니다. 맞으면 이름을 눌러 저장하고, 틀리면 수정하세요.',
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 5, vertical: 1),
                        decoration: BoxDecoration(
                          borderRadius: AppRadius.brSm,
                          border: Border.all(color: color.withAlpha(130)),
                        ),
                        child: Text(
                          '추정됨',
                          style: TextStyle(
                            color: color,
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ],
                  if (startTime != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      _formatTimeRange(startTime!, endTime),
                      style: TextStyle(
                        color: scheme.textTertiary,
                        fontSize: 11,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: isHighlighted
                    ? color.withAlpha(scheme.isDark ? 36 : 24)
                    : scheme.surface,
                borderRadius: AppRadius.brMd,
                border: Border.all(
                  color: isHighlighted ? color : scheme.border,
                  width: 1,
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
    final scheme = AppColors.of(context);
    if (searchQuery == null || searchQuery!.isEmpty) {
      return Text(
        text,
        style: TextStyle(fontSize: 14, height: 1.5, color: scheme.textPrimary),
      );
    }

    final matches = RegExp(RegExp.escape(searchQuery!), caseSensitive: false)
        .allMatches(text)
        .toList();
    if (matches.isEmpty) {
      return Text(
        text,
        style: TextStyle(fontSize: 14, height: 1.5, color: scheme.textPrimary),
      );
    }

    final spans = <TextSpan>[];
    int lastMatchEnd = 0;
    // 검색 하이라이트 — 다크모드에서는 앰버 배경 + 흰 글자, 라이트에서는 노란 배경 + 검은 글자
    final highlightBg =
        scheme.isDark ? const Color(0xCCF59E0B) : const Color(0xCCFDE047);

    for (final match in matches) {
      if (match.start > lastMatchEnd) {
        spans.add(TextSpan(text: text.substring(lastMatchEnd, match.start)));
      }
      spans.add(TextSpan(
        text: text.substring(match.start, match.end),
        style:
            TextStyle(backgroundColor: highlightBg, color: scheme.textPrimary),
      ));
      lastMatchEnd = match.end;
    }

    if (lastMatchEnd < text.length) {
      spans.add(TextSpan(text: text.substring(lastMatchEnd)));
    }

    return RichText(
      text: TextSpan(
        style: DefaultTextStyle.of(context).style.copyWith(
              fontSize: 14,
              height: 1.5,
              color: scheme.textPrimary,
            ),
        children: spans,
      ),
    );
  }

  String _formatTime(Duration duration) {
    final minutes = duration.inMinutes;
    final seconds = duration.inSeconds % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}';
  }

  String _formatTimeRange(Duration start, Duration? end) {
    if (end == null || end <= start) {
      return _formatTime(start);
    }
    return '${_formatTime(start)} - ${_formatTime(end)}';
  }
}
