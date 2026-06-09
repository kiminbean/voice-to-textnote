// ProcessingStats, DailyStats 모델 테스트
// SPEC-APP-005 REQ-019,021
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/models/processing_stats.dart';

void main() {
  group('DailyStats 모델', () {
    test('생성자가 모든 필드를 올바르게 설정해야 함', () {
      final date = DateTime(2026, 6, 9);
      final stats = DailyStats(
        date: date,
        count: 10,
        successCount: 8,
        failCount: 2,
        avgProcessingSeconds: 45.5,
      );

      expect(stats.date, date);
      expect(stats.count, 10);
      expect(stats.successCount, 8);
      expect(stats.failCount, 2);
      expect(stats.avgProcessingSeconds, 45.5);
    });

    test('successRate가 올바르게 계산되어야 함', () {
      final date = DateTime(2026, 6, 9);

      // 정상 케이스: 8/10 = 0.8
      final stats80 = DailyStats(
        date: date,
        count: 10,
        successCount: 8,
        failCount: 2,
        avgProcessingSeconds: 30.0,
      );
      expect(stats80.successRate, closeTo(0.8, 0.001));

      // 100% 성공
      final stats100 = DailyStats(
        date: date,
        count: 5,
        successCount: 5,
        failCount: 0,
        avgProcessingSeconds: 20.0,
      );
      expect(stats100.successRate, 1.0);

      // 0% 성공
      final stats0 = DailyStats(
        date: date,
        count: 3,
        successCount: 0,
        failCount: 3,
        avgProcessingSeconds: 0.0,
      );
      expect(stats0.successRate, 0.0);
    });

    test('count가 0이면 successRate는 0.0이어야 함', () {
      final date = DateTime(2026, 6, 9);
      final stats = DailyStats(
        date: date,
        count: 0,
        successCount: 0,
        failCount: 0,
        avgProcessingSeconds: 0.0,
      );

      expect(stats.successRate, 0.0);
    });
  });

  group('ProcessingStats 모델', () {
    test('생성자가 모든 필드를 올바르게 설정해야 함', () {
      final stats = ProcessingStats(
        totalCount: 100,
        successCount: 90,
        failCount: 10,
        successRate: 0.9,
        avgProcessingTime: const Duration(seconds: 45),
        avgStageDurations: {
          PipelineStep.uploading: const Duration(seconds: 5),
          PipelineStep.transcribing: const Duration(seconds: 20),
        },
        dailyStats: const [],
      );

      expect(stats.totalCount, 100);
      expect(stats.successCount, 90);
      expect(stats.failCount, 10);
      expect(stats.successRate, 0.9);
      expect(stats.avgProcessingTime, const Duration(seconds: 45));
      expect(stats.avgStageDurations.length, 2);
      expect(stats.dailyStats, isEmpty);
    });

    test('empty 팩토리가 기본값을 가져야 함', () {
      final stats = ProcessingStats.empty();

      expect(stats.totalCount, 0);
      expect(stats.successCount, 0);
      expect(stats.failCount, 0);
      expect(stats.successRate, 0.0);
      expect(stats.avgProcessingTime, Duration.zero);
      expect(stats.avgStageDurations, isEmpty);
      expect(stats.dailyStats, isEmpty);
    });

    test('getAvgStageDuration이 올바른 Duration을 반환해야 함', () {
      final stats = ProcessingStats(
        totalCount: 10,
        successCount: 10,
        failCount: 0,
        successRate: 1.0,
        avgProcessingTime: const Duration(seconds: 60),
        avgStageDurations: {
          PipelineStep.uploading: const Duration(seconds: 5),
          PipelineStep.transcribing: const Duration(seconds: 30),
          PipelineStep.summarizing: const Duration(seconds: 15),
        },
        dailyStats: const [],
      );

      expect(
        stats.getAvgStageDuration(PipelineStep.uploading),
        const Duration(seconds: 5),
      );
      expect(
        stats.getAvgStageDuration(PipelineStep.transcribing),
        const Duration(seconds: 30),
      );
      expect(
        stats.getAvgStageDuration(PipelineStep.diarizing),
        isNull,
      );
    });

    test('empty 통계에서 getAvgStageDuration은 null을 반환해야 함', () {
      final stats = ProcessingStats.empty();

      expect(stats.getAvgStageDuration(PipelineStep.uploading), isNull);
      expect(stats.getAvgStageDuration(PipelineStep.transcribing), isNull);
    });

    test('dailyStats가 여러 일별 데이터를 가질 수 있어야 함', () {
      final daily1 = DailyStats(
        date: DateTime(2026, 6, 8),
        count: 5,
        successCount: 4,
        failCount: 1,
        avgProcessingSeconds: 30.0,
      );
      final daily2 = DailyStats(
        date: DateTime(2026, 6, 9),
        count: 8,
        successCount: 7,
        failCount: 1,
        avgProcessingSeconds: 25.0,
      );

      final stats = ProcessingStats(
        totalCount: 13,
        successCount: 11,
        failCount: 2,
        successRate: 11 / 13,
        avgProcessingTime: const Duration(seconds: 27),
        avgStageDurations: const {},
        dailyStats: [daily1, daily2],
      );

      expect(stats.dailyStats.length, 2);
      expect(stats.dailyStats[0].count, 5);
      expect(stats.dailyStats[1].count, 8);
    });
  });
}
