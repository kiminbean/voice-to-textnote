// 통계 상태 관리 프로바이더
// @MX:NOTE: SPEC-APP-005 REQ-019,020,021 — 통계 데이터 제공

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/processing_stats.dart';
import 'package:voice_to_textnote/services/stats_service.dart';

class StatsState {
  final bool isLoading;
  final ProcessingStats? stats;
  final String? error;

  const StatsState({
    required this.isLoading,
    this.stats,
    this.error,
  });

  factory StatsState.initial() => const StatsState(isLoading: false);

  StatsState copyWith({
    bool? isLoading,
    ProcessingStats? stats,
    String? error,
  }) =>
      StatsState(
        isLoading: isLoading ?? this.isLoading,
        stats: stats ?? this.stats,
        error: error,
      );
}

class StatsNotifier extends Notifier<StatsState> {
  @override
  StatsState build() => StatsState.initial();

  /// 통계 조회
  Future<void> loadStats() async {
    state = state.copyWith(isLoading: true);
    try {
      final service = StatsService();
      await service.init();
      final stats = await service.getStats();
      state = StatsState(isLoading: false, stats: stats);
    } catch (e) {
      state = StatsState(isLoading: false, error: e.toString());
    }
  }
}

final statsProvider = NotifierProvider<StatsNotifier, StatsState>(
  StatsNotifier.new,
);
