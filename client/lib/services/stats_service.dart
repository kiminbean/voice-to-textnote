// 처리 통계 수집/조회 서비스
// @MX:NOTE: SPEC-APP-005 REQ-019,021 — Hive에서 처리 이벤트 집계

import 'dart:convert';
import 'package:hive/hive.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/models/processing_stats.dart';

/// 처리 이벤트 기록
class ProcessingEvent {
  final String meetingId;
  final DateTime completedAt;
  final bool success;
  final Duration totalDuration;
  final Map<String, int> stageDurationsMs;

  const ProcessingEvent({
    required this.meetingId,
    required this.completedAt,
    required this.success,
    required this.totalDuration,
    required this.stageDurationsMs,
  });

  Map<String, dynamic> toJson() => {
        'meetingId': meetingId,
        'completedAt': completedAt.toIso8601String(),
        'success': success,
        'totalDurationMs': totalDuration.inMilliseconds,
        'stageDurationsMs': stageDurationsMs,
      };

  factory ProcessingEvent.fromJson(Map<String, dynamic> json) => ProcessingEvent(
        meetingId: json['meetingId'] as String,
        completedAt: DateTime.parse(json['completedAt'] as String),
        success: json['success'] as bool,
        totalDuration: Duration(milliseconds: json['totalDurationMs'] as int),
        stageDurationsMs: Map<String, int>.from(json['stageDurationsMs'] as Map),
      );
}

/// 통계 서비스 (REQ-019, REQ-021)
class StatsService {
  static const String _eventsBoxName = 'processing_events';

  Box<String>? _eventsBox;

  Future<void> init() async {
    _eventsBox = await Hive.openBox<String>(_eventsBoxName);
  }

  /// 처리 완료 이벤트 기록 (REQ-021)
  Future<void> recordEvent({
    required String meetingId,
    required bool success,
    required Duration totalDuration,
    required Map<PipelineStep, StageTiming> stageTimings,
  }) async {
    if (_eventsBox == null) await init();

    final stageDurationsMs = <String, int>{};
    for (final entry in stageTimings.entries) {
      stageDurationsMs[entry.key.name] = entry.value.duration.inMilliseconds;
    }

    final event = ProcessingEvent(
      meetingId: meetingId,
      completedAt: DateTime.now(),
      success: success,
      totalDuration: totalDuration,
      stageDurationsMs: stageDurationsMs,
    );

    await _eventsBox!.put(meetingId, jsonEncode(event.toJson()));
  }

  /// 최근 30일 통계 집계 (REQ-019, REQ-020)
  Future<ProcessingStats> getStats() async {
    if (_eventsBox == null) await init();

    final now = DateTime.now();
    final thirtyDaysAgo = now.subtract(const Duration(days: 30));

    final events = <ProcessingEvent>[];
    for (final eventJson in _eventsBox!.values) {
      try {
        final event = ProcessingEvent.fromJson(
          jsonDecode(eventJson) as Map<String, dynamic>,
        );
        if (event.completedAt.isAfter(thirtyDaysAgo)) {
          events.add(event);
        }
      } catch (_) {}
    }

    if (events.isEmpty) return ProcessingStats.empty();

    // 종합 통계 계산
    final successEvents = events.where((e) => e.success).toList();
    final totalMs = events.fold<int>(
      0,
      (sum, e) => sum + e.totalDuration.inMilliseconds,
    );

    // 단계별 평균 소요 시간
    final stageSums = <String, int>{};
    final stageCounts = <String, int>{};
    for (final event in successEvents) {
      for (final entry in event.stageDurationsMs.entries) {
        stageSums[entry.key] = (stageSums[entry.key] ?? 0) + entry.value;
        stageCounts[entry.key] = (stageCounts[entry.key] ?? 0) + 1;
      }
    }

    final avgStageDurations = <PipelineStep, Duration>{};
    for (final entry in stageSums.entries) {
      final step = PipelineStep.values.where((s) => s.name == entry.key).firstOrNull;
      if (step != null) {
        final count = stageCounts[entry.key] ?? 1;
        avgStageDurations[step] = Duration(milliseconds: entry.value ~/ count);
      }
    }

    // 일별 통계
    final dailyMap = <String, _DayBuilder>{};
    for (final event in events) {
      final dayKey =
          '${event.completedAt.year}-${event.completedAt.month.toString().padLeft(2, '0')}-${event.completedAt.day.toString().padLeft(2, '0')}';
      final builder = dailyMap.putIfAbsent(dayKey, () => _DayBuilder(date: event.completedAt));
      builder.add(event);
    }

    final dailyStats = dailyMap.values.map((b) => b.build()).toList()
      ..sort((a, b) => a.date.compareTo(b.date));

    return ProcessingStats(
      totalCount: events.length,
      successCount: successEvents.length,
      failCount: events.length - successEvents.length,
      successRate: events.isNotEmpty ? successEvents.length / events.length : 0.0,
      avgProcessingTime: Duration(milliseconds: totalMs ~/ events.length),
      avgStageDurations: avgStageDurations,
      dailyStats: dailyStats,
    );
  }
}

/// 일별 통계 빌더
class _DayBuilder {
  final DateTime date;
  int count = 0;
  int successCount = 0;
  int failCount = 0;
  int totalMs = 0;

  _DayBuilder({required this.date});

  void add(ProcessingEvent event) {
    count++;
    if (event.success) {
      successCount++;
      totalMs += event.totalDuration.inMilliseconds;
    } else {
      failCount++;
    }
  }

  DailyStats build() => DailyStats(
        date: DateTime(date.year, date.month, date.day),
        count: count,
        successCount: successCount,
        failCount: failCount,
        avgProcessingSeconds: successCount > 0 ? totalMs / successCount / 1000 : 0,
      );
}
