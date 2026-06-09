// CacheEntry 모델 및 CacheService 상수 테스트
// SPEC-APP-005 REQ-016,018
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/cache_service.dart';

void main() {
  group('CacheEntry 모델', () {
    test('생성자가 모든 필드를 올바르게 설정해야 함', () {
      final cachedAt = DateTime(2026, 6, 9, 12, 0, 0);
      final entry = CacheEntry(
        key: 'meeting-001',
        cachedAt: cachedAt,
        sizeBytes: 1024,
      );

      expect(entry.key, 'meeting-001');
      expect(entry.cachedAt, cachedAt);
      expect(entry.sizeBytes, 1024);
    });

    test('toJson이 올바른 JSON 맵을 생성해야 함', () {
      final cachedAt = DateTime(2026, 6, 9, 12, 30, 0);
      final entry = CacheEntry(
        key: 'meeting-002',
        cachedAt: cachedAt,
        sizeBytes: 2048,
      );

      final json = entry.toJson();

      expect(json['key'], 'meeting-002');
      expect(json['cachedAt'], cachedAt.toIso8601String());
      expect(json['sizeBytes'], 2048);
    });

    test('fromJson이 올바른 CacheEntry를 생성해야 함', () {
      final cachedAt = DateTime(2026, 6, 9, 12, 30, 0);
      final json = {
        'key': 'meeting-003',
        'cachedAt': cachedAt.toIso8601String(),
        'sizeBytes': 4096,
      };

      final entry = CacheEntry.fromJson(json);

      expect(entry.key, 'meeting-003');
      expect(entry.cachedAt, cachedAt);
      expect(entry.sizeBytes, 4096);
    });

    test('toJson/fromJson 라운드트립이 동일한 값을 보존해야 함', () {
      final cachedAt = DateTime(2026, 6, 9, 15, 45, 30);
      final original = CacheEntry(
        key: 'round-trip-test',
        cachedAt: cachedAt,
        sizeBytes: 8192,
      );

      final json = original.toJson();
      final restored = CacheEntry.fromJson(json);

      expect(restored.key, original.key);
      expect(restored.cachedAt, original.cachedAt);
      expect(restored.sizeBytes, original.sizeBytes);
    });

    test('JSON 문자열 직렬화/역직렬화 라운드트립이 동작해야 함', () {
      final cachedAt = DateTime(2026, 6, 9, 10, 0, 0);
      final original = CacheEntry(
        key: 'json-encode-test',
        cachedAt: cachedAt,
        sizeBytes: 512,
      );

      final jsonString = jsonEncode(original.toJson());
      final decoded = CacheEntry.fromJson(
        jsonDecode(jsonString) as Map<String, dynamic>,
      );

      expect(decoded.key, original.key);
      expect(decoded.cachedAt, original.cachedAt);
      expect(decoded.sizeBytes, original.sizeBytes);
    });

    test('다양한 sizeBytes 값으로 CacheEntry를 생성할 수 있어야 함', () {
      final cachedAt = DateTime(2026, 6, 9);

      // 0바이트
      final zero = CacheEntry(key: 'zero', cachedAt: cachedAt, sizeBytes: 0);
      expect(zero.sizeBytes, 0);

      // 큰 파일 (100MB)
      final large = CacheEntry(
        key: 'large',
        cachedAt: cachedAt,
        sizeBytes: 100 * 1024 * 1024,
      );
      expect(large.sizeBytes, 104857600);
    });
  });

  group('CacheService 상수', () {
    test('maxCacheBytes는 500MB여야 함', () {
      const expected = 500 * 1024 * 1024;
      expect(CacheService.maxCacheBytes, expected);
    });
  });

  group('CacheService 인스턴스', () {
    test('초기화 전에는 entryCount가 0이어야 함', () {
      final service = CacheService();

      // Hive 미초기화 상태에서는 _cacheBox가 null
      // 따라서 entryCount는 0 (null 체크 후 ?? 0)
      expect(service.entryCount, 0);
    });

    test('초기화 전에는 totalSizeBytes가 0이어야 함', () {
      final service = CacheService();

      expect(service.totalSizeBytes, 0);
    });

    test('초기화 전에는 get이 null을 반환해야 함', () {
      final service = CacheService();

      expect(service.get('any-key'), isNull);
    });

    test('초기화 전에는 contains가 false를 반환해야 함', () {
      final service = CacheService();

      expect(service.contains('any-key'), isFalse);
    });

    test('초기화 전에는 getCachedAt이 null을 반환해야 함', () {
      final service = CacheService();

      expect(service.getCachedAt('any-key'), isNull);
    });
  });
}
