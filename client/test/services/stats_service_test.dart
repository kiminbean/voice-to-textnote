// ProcessingEvent 모델 및 StatsService 테스트
// SPEC-APP-005 REQ-019,021
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/services/stats_service.dart';

void main() {
  group('ProcessingEvent 모델', () {
    final fixedTime = DateTime(2026, 6, 9, 14, 30, 0);

    test('생성자가 모든 필드를 올바르게 설정해야 함', () {
      final event = ProcessingEvent(
        meetingId: 'mtg-001',
        completedAt: fixedTime,
        success: true,
        totalDuration: const Duration(seconds: 60),
        stageDurationsMs: {'uploading': 5000, 'transcribing': 30000},
      );

      expect(event.meetingId, 'mtg-001');
      expect(event.completedAt, fixedTime);
      expect(event.success, isTrue);
      expect(event.totalDuration, const Duration(seconds: 60));
      expect(event.stageDurationsMs['uploading'], 5000);
      expect(event.stageDurationsMs['transcribing'], 30000);
    });

    test('toJson이 올바른 JSON 맵을 생성해야 함', () {
      final event = ProcessingEvent(
        meetingId: 'mtg-002',
        completedAt: fixedTime,
        success: false,
        totalDuration: const Duration(seconds: 30),
        stageDurationsMs: {'uploading': 5000},
      );

      final json = event.toJson();

      expect(json['meetingId'], 'mtg-002');
      expect(json['completedAt'], fixedTime.toIso8601String());
      expect(json['success'], isFalse);
      expect(json['totalDurationMs'], 30000);
      expect(json['stageDurationsMs'], {'uploading': 5000});
    });

    test('fromJson이 올바른 ProcessingEvent를 생성해야 함', () {
      final json = {
        'meetingId': 'mtg-003',
        'completedAt': fixedTime.toIso8601String(),
        'success': true,
        'totalDurationMs': 120000,
        'stageDurationsMs': {'uploading': 5000, 'transcribing': 60000},
      };

      final event = ProcessingEvent.fromJson(json);

      expect(event.meetingId, 'mtg-003');
      expect(event.completedAt, fixedTime);
      expect(event.success, isTrue);
      expect(event.totalDuration, const Duration(milliseconds: 120000));
      expect(event.stageDurationsMs['uploading'], 5000);
      expect(event.stageDurationsMs['transcribing'], 60000);
    });

    test('toJson/fromJson 라운드트립이 동일한 값을 보존해야 함', () {
      final original = ProcessingEvent(
        meetingId: 'round-trip',
        completedAt: fixedTime,
        success: true,
        totalDuration: const Duration(seconds: 90),
        stageDurationsMs: {
          'uploading': 3000,
          'transcribing': 45000,
          'summarizing': 20000,
        },
      );

      final json = original.toJson();
      final restored = ProcessingEvent.fromJson(json);

      expect(restored.meetingId, original.meetingId);
      expect(restored.completedAt, original.completedAt);
      expect(restored.success, original.success);
      expect(restored.totalDuration, original.totalDuration);
      expect(restored.stageDurationsMs, original.stageDurationsMs);
    });

    test('JSON 문자열 직렬화/역직렬화 라운드트립이 동작해야 함', () {
      final original = ProcessingEvent(
        meetingId: 'json-encode',
        completedAt: fixedTime,
        success: false,
        totalDuration: const Duration(milliseconds: 500),
        stageDurationsMs: {},
      );

      final jsonString = jsonEncode(original.toJson());
      final decoded = ProcessingEvent.fromJson(
        jsonDecode(jsonString) as Map<String, dynamic>,
      );

      expect(decoded.meetingId, original.meetingId);
      expect(decoded.success, original.success);
      expect(decoded.totalDuration, original.totalDuration);
      expect(decoded.stageDurationsMs, isEmpty);
    });

    test('빈 stageDurationsMs로 생성할 수 있어야 함', () {
      final event = ProcessingEvent(
        meetingId: 'empty-stages',
        completedAt: fixedTime,
        success: true,
        totalDuration: Duration.zero,
        stageDurationsMs: const {},
      );

      expect(event.stageDurationsMs, isEmpty);
    });

    test('실패 이벤트를 올바르게 생성할 수 있어야 함', () {
      final event = ProcessingEvent(
        meetingId: 'failed-mtg',
        completedAt: fixedTime,
        success: false,
        totalDuration: const Duration(seconds: 15),
        stageDurationsMs: {'uploading': 15000},
      );

      expect(event.success, isFalse);
      expect(event.totalDuration, const Duration(seconds: 15));
    });
  });

  group('StatsService 인스턴스', () {
    test('인스턴스를 생성할 수 있어야 함', () {
      final service = StatsService();

      expect(service, isNotNull);
    });
  });
}
