// 처리 통계 모델
// @MX:NOTE: SPEC-APP-005 REQ-019,021 — 총 건수, 평균 시간, 성공률, 단계별 평균

import 'package:voice_to_textnote/models/pipeline_state.dart';

/// 일별 통계 데이터
class DailyStats {
  final DateTime date;
  final int count;
  final int successCount;
  final int failCount;
  final double avgProcessingSeconds;

  const DailyStats({
    required this.date,
    required this.count,
    required this.successCount,
    required this.failCount,
    required this.avgProcessingSeconds,
  });

  double get successRate => count > 0 ? successCount / count : 0.0;
}

/// 처리 통계 종합 모델 (REQ-019)
class ProcessingStats {
  final int totalCount;
  final int successCount;
  final int failCount;
  final double successRate;
  final Duration avgProcessingTime;
  final Map<PipelineStep, Duration> avgStageDurations;
  final List<DailyStats> dailyStats;

  const ProcessingStats({
    required this.totalCount,
    required this.successCount,
    required this.failCount,
    required this.successRate,
    required this.avgProcessingTime,
    required this.avgStageDurations,
    required this.dailyStats,
  });

  /// 빈 통계
  factory ProcessingStats.empty() => const ProcessingStats(
        totalCount: 0,
        successCount: 0,
        failCount: 0,
        successRate: 0.0,
        avgProcessingTime: Duration.zero,
        avgStageDurations: {},
        dailyStats: [],
      );

  /// 특정 단계의 평균 소요 시간 (REQ-021)
  Duration? getAvgStageDuration(PipelineStep step) => avgStageDurations[step];
}
