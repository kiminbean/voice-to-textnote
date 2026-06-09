// CacheSyncProvider 상태 관리 테스트
// SPEC-APP-005 REQ-017 — 캐시-서버 불일치 감지
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/providers/cache_provider.dart';

void main() {
  group('CacheSyncState', () {
    test('initial()은 기본값을 가져야 함', () {
      // Act
      final state = CacheSyncState.initial();

      // Assert
      expect(state.staleEntries, isEmpty);
      expect(state.isChecking, false);
    });

    test('isStale() - 존재하지 않는 키는 false를 반환해야 함', () {
      // Arrange
      final state = CacheSyncState.initial();

      // Act & Assert
      expect(state.isStale('nonexistent-id'), false);
    });

    test('isStale() - stale 항목은 true를 반환해야 함', () {
      // Arrange
      const state = CacheSyncState(
        staleEntries: {'meeting-1': true, 'meeting-2': false},
        isChecking: false,
      );

      // Act & Assert
      expect(state.isStale('meeting-1'), true);
      expect(state.isStale('meeting-2'), false);
    });
  });

  group('CacheSyncNotifier', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
    });

    test('초기 상태는 CacheSyncState.initial()이어야 함', () {
      // Act
      final state = container.read(cacheSyncProvider);

      // Assert
      expect(state.staleEntries, isEmpty);
      expect(state.isChecking, false);
    });

    test('checkSync() — 1시간 이내 항목은 stale이 아니어야 함', () async {
      // Arrange: 30분 전 항목
      final now = DateTime.now();
      final recentDates = {
        'meeting-recent': now.subtract(const Duration(minutes: 30)),
      };

      // Act
      await container.read(cacheSyncProvider.notifier).checkSync(recentDates);
      final state = container.read(cacheSyncProvider);

      // Assert
      expect(state.isChecking, false);
      expect(state.isStale('meeting-recent'), false);
    });

    test('checkSync() — 1시간 초과 항목은 stale이어야 함', () async {
      // Arrange: 2시간 전 항목
      final now = DateTime.now();
      final oldDates = {
        'meeting-old': now.subtract(const Duration(hours: 2)),
      };

      // Act
      await container.read(cacheSyncProvider.notifier).checkSync(oldDates);
      final state = container.read(cacheSyncProvider);

      // Assert
      expect(state.isChecking, false);
      expect(state.isStale('meeting-old'), true);
    });

    test('checkSync() — 여러 항목이 섞여 있을 때 올바르게 분류해야 함', () async {
      // Arrange
      final now = DateTime.now();
      final mixedDates = {
        'fresh': now.subtract(const Duration(minutes: 10)),
        'stale': now.subtract(const Duration(hours: 3)),
        'borderline': now.subtract(const Duration(hours: 2, minutes: 30)),
      };

      // Act
      await container.read(cacheSyncProvider.notifier).checkSync(mixedDates);
      final state = container.read(cacheSyncProvider);

      // Assert
      expect(state.isStale('fresh'), false);
      expect(state.isStale('stale'), true);
      expect(state.isStale('borderline'), true);
    });

    test('checkSync() — 빈 맵을 전달하면 아무 항목도 stale이 아니어야 함', () async {
      // Act
      await container.read(cacheSyncProvider.notifier).checkSync({});
      final state = container.read(cacheSyncProvider);

      // Assert
      expect(state.staleEntries, isEmpty);
      expect(state.isChecking, false);
    });
  });
}
