// StatsProvider 상태 관리 테스트
// SPEC-APP-005 REQ-019,020,021 — 통계 데이터 제공
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/processing_stats.dart';
import 'package:voice_to_textnote/providers/stats_provider.dart';

void main() {
  group('StatsState', () {
    test('initial()은 기본값을 가져야 함', () {
      // Act
      final state = StatsState.initial();

      // Assert
      expect(state.isLoading, false);
      expect(state.stats, isNull);
      expect(state.error, isNull);
    });

    test('copyWith()가 지정된 필드만 변경해야 함', () {
      // Arrange
      const original = StatsState(isLoading: false);

      // Act — isLoading만 변경
      final updated = original.copyWith(isLoading: true);

      // Assert
      expect(updated.isLoading, true);
      expect(updated.stats, isNull);
      expect(updated.error, isNull);
    });

    test('copyWith()로 stats를 설정할 수 있어야 함', () {
      // Arrange
      const original = StatsState(isLoading: false);
      final dummyStats = ProcessingStats.empty();

      // Act
      final updated = original.copyWith(stats: dummyStats);

      // Assert
      expect(updated.isLoading, false);
      expect(updated.stats, isNotNull);
      expect(updated.stats!.totalCount, 0);
    });

    test('copyWith()로 error를 설정할 수 있어야 함', () {
      // Arrange
      const original = StatsState(isLoading: false);

      // Act
      final updated = original.copyWith(error: '네트워크 오류');

      // Assert
      expect(updated.isLoading, false);
      expect(updated.error, '네트워크 오류');
    });
  });

  group('StatsNotifier', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
    });

    test('초기 상태는 StatsState.initial()이어야 함', () {
      // Act
      final state = container.read(statsProvider);

      // Assert
      expect(state.isLoading, false);
      expect(state.stats, isNull);
      expect(state.error, isNull);
    });

    test('build()는 isLoading이 false인 상태를 반환해야 함', () {
      // Act
      final state = container.read(statsProvider);

      // Assert
      expect(state.isLoading, false);
    });
  });
}
