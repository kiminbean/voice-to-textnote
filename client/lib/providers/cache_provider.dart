// 캐시 동기화 상태 프로바이더
// @MX:NOTE: SPEC-APP-005 REQ-017 — 캐시-서버 불일치 감지

import 'package:flutter_riverpod/flutter_riverpod.dart';

class CacheSyncState {
  final Map<String, bool> staleEntries; // meetingId → isStale
  final bool isChecking;

  const CacheSyncState({
    required this.staleEntries,
    required this.isChecking,
  });

  factory CacheSyncState.initial() =>
      const CacheSyncState(staleEntries: {}, isChecking: false);

  bool isStale(String meetingId) => staleEntries[meetingId] ?? false;
}

class CacheSyncNotifier extends Notifier<CacheSyncState> {
  @override
  CacheSyncState build() => CacheSyncState.initial();

  /// 캐시-서버 동기화 체크 (REQ-017)
  Future<void> checkSync(Map<String, DateTime> cachedDates) async {
    state = const CacheSyncState(
      staleEntries: {},
      isChecking: true,
    );

    // TODO: 실제 서버 API와 비교 로직
    // 현재는 캐시가 1시간 이상 된 항목을 stale로 표시
    final now = DateTime.now();
    final stale = <String, bool>{};

    for (final entry in cachedDates.entries) {
      final age = now.difference(entry.value);
      stale[entry.key] = age.inHours > 1;
    }

    state = CacheSyncState(staleEntries: stale, isChecking: false);
  }
}

final cacheSyncProvider = NotifierProvider<CacheSyncNotifier, CacheSyncState>(
  CacheSyncNotifier.new,
);
