// Hive 기반 오프라인 캐시 서비스
// @MX:NOTE: SPEC-APP-005 REQ-016,018 — 500MB LRU 자동 삭제 포함 오프라인 캐싱

import 'dart:convert';
import 'package:hive/hive.dart';

/// 캐시 엔트리 메타데이터
class CacheEntry {
  final String key;
  final DateTime cachedAt;
  final int sizeBytes;

  const CacheEntry({
    required this.key,
    required this.cachedAt,
    required this.sizeBytes,
  });

  Map<String, dynamic> toJson() => {
        'key': key,
        'cachedAt': cachedAt.toIso8601String(),
        'sizeBytes': sizeBytes,
      };

  factory CacheEntry.fromJson(Map<String, dynamic> json) => CacheEntry(
        key: json['key'] as String,
        cachedAt: DateTime.parse(json['cachedAt'] as String),
        sizeBytes: json['sizeBytes'] as int,
      );
}

/// 오프라인 캐시 서비스 (REQ-016, REQ-018)
class CacheService {
  static const String _cacheBoxName = 'pipeline_results';
  static const String _metaBoxName = 'cache_meta';

  /// 최대 캐시 크기 (500MB)
  static const int maxCacheBytes = 500 * 1024 * 1024;

  Box<String>? _cacheBox;
  Box<String>? _metaBox;

  /// 초기화 (main.dart에서 호출)
  Future<void> init() async {
    _cacheBox = await Hive.openBox<String>(_cacheBoxName);
    _metaBox = await Hive.openBox<String>(_metaBoxName);
  }

  /// 결과 캐싱 (REQ-016)
  Future<void> put(String meetingId, Map<String, dynamic> result) async {
    if (_cacheBox == null) return;

    final jsonStr = jsonEncode(result);
    final sizeBytes = jsonStr.length;

    // 캐시 저장
    await _cacheBox!.put(meetingId, jsonStr);

    // 메타데이터 업데이트
    final meta = CacheEntry(
      key: meetingId,
      cachedAt: DateTime.now(),
      sizeBytes: sizeBytes,
    );
    await _metaBox!.put(meetingId, jsonEncode(meta.toJson()));

    // LRU 삭제 체크 (REQ-018)
    await _enforceMaxSize();
  }

  /// 캐시된 결과 조회 (REQ-016)
  Map<String, dynamic>? get(String meetingId) {
    final jsonStr = _cacheBox?.get(meetingId);
    if (jsonStr == null) return null;
    try {
      return jsonDecode(jsonStr) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  /// 캐시 존재 여부
  bool contains(String meetingId) => _cacheBox?.containsKey(meetingId) ?? false;

  /// 캐시 삭제
  Future<void> remove(String meetingId) async {
    await _cacheBox?.delete(meetingId);
    await _metaBox?.delete(meetingId);
  }

  /// 캐시-서버 비교를 위한 타임스탬프 조회 (REQ-017)
  DateTime? getCachedAt(String meetingId) {
    final metaJson = _metaBox?.get(meetingId);
    if (metaJson == null) return null;
    try {
      final meta = CacheEntry.fromJson(
        jsonDecode(metaJson) as Map<String, dynamic>,
      );
      return meta.cachedAt;
    } catch (_) {
      return null;
    }
  }

  /// 전체 캐시 크기
  int get totalSizeBytes {
    int total = 0;
    for (final String metaJson in _metaBox?.values ?? <String>[]) {
      try {
        final meta = CacheEntry.fromJson(
          jsonDecode(metaJson) as Map<String, dynamic>,
        );
        total += meta.sizeBytes;
      } catch (_) {}
    }
    return total;
  }

  /// 캐시 엔트리 수
  int get entryCount => _cacheBox?.length ?? 0;

  /// LRU 삭제 실행 (500MB 초과 시 가장 오래된 항목 삭제, REQ-018)
  Future<void> _enforceMaxSize() async {
    var currentSize = totalSizeBytes;
    if (currentSize <= maxCacheBytes) return;

    // 모든 엔트리를 시간순 정렬 (오래된 것 먼저)
    final entries = <CacheEntry>[];
    for (final String metaJson in _metaBox?.values ?? <String>[]) {
      try {
        entries.add(
          CacheEntry.fromJson(jsonDecode(metaJson) as Map<String, dynamic>),
        );
      } catch (_) {}
    }
    entries.sort((a, b) => a.cachedAt.compareTo(b.cachedAt));

    // 오래된 것부터 삭제하여 한계 이하로
    for (final entry in entries) {
      if (currentSize <= maxCacheBytes) break;
      await remove(entry.key);
      currentSize -= entry.sizeBytes;
    }
  }

  /// 전체 캐시 비우기
  Future<void> clear() async {
    await _cacheBox?.clear();
    await _metaBox?.clear();
  }
}
