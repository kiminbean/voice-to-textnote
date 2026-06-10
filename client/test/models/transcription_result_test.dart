import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/transcription_result.dart';

void main() {
  group('TranscriptionSegment', () {
    test('creates segment with all fields', () {
      final segment = TranscriptionSegment(
        startTime: Duration(seconds: 0),
        endTime: Duration(seconds: 5),
        text: '안녕하세요',
        speaker: 'SPEAKER_1',
      );

      expect(segment.startTime, Duration(seconds: 0));
      expect(segment.endTime, Duration(seconds: 5));
      expect(segment.text, '안녕하세요');
      expect(segment.speaker, 'SPEAKER_1');
    });

    test('creates segment without speaker', () {
      final segment = TranscriptionSegment(
        startTime: Duration(seconds: 5),
        endTime: Duration(seconds: 10),
        text: '반갑습니다',
      );

      expect(segment.speaker, isNull);
    });

    test('copyWith updates specified fields', () {
      final original = TranscriptionSegment(
        startTime: Duration(seconds: 0),
        endTime: Duration(seconds: 5),
        text: '안녕하세요',
        speaker: 'SPEAKER_1',
      );

      final updated = original.copyWith(
        text: '반갑습니다',
        speaker: 'SPEAKER_2',
      );

      expect(updated.startTime, original.startTime);
      expect(updated.endTime, original.endTime);
      expect(updated.text, '반갑습니다');
      expect(updated.speaker, 'SPEAKER_2');
    });

    test('fromJson creates segment from JSON', () {
      final json = {
        'start_time': 1000, // milliseconds
        'end_time': 5000,
        'text': '안녕하세요',
        'speaker': 'SPEAKER_1',
      };

      final segment = TranscriptionSegment.fromJson(json);

      expect(segment.startTime, Duration(milliseconds: 1000));
      expect(segment.endTime, Duration(milliseconds: 5000));
      expect(segment.text, '안녕하세요');
      expect(segment.speaker, 'SPEAKER_1');
    });

    test('fromJson handles null speaker', () {
      final json = {
        'start_time': 5000,
        'end_time': 10000,
        'text': '반갑습니다',
        'speaker': null,
      };

      final segment = TranscriptionSegment.fromJson(json);

      expect(segment.speaker, isNull);
    });

    test('toJson serializes segment to JSON', () {
      final segment = TranscriptionSegment(
        startTime: Duration(milliseconds: 1000),
        endTime: Duration(milliseconds: 5000),
        text: '안녕하세요',
        speaker: 'SPEAKER_1',
      );

      final json = segment.toJson();

      expect(json['start_time'], 1000);
      expect(json['end_time'], 5000);
      expect(json['text'], '안녕하세요');
      expect(json['speaker'], 'SPEAKER_1');
    });

    test('toJson handles null speaker', () {
      final segment = TranscriptionSegment(
        startTime: Duration(milliseconds: 5000),
        endTime: Duration(milliseconds: 10000),
        text: '반갑습니다',
      );

      final json = segment.toJson();

      expect(json['speaker'], isNull);
    });
  });

  group('TranscriptionResult', () {
    test('creates offline result using factory constructor', () {
      final result = TranscriptionResult.offline(
        text: '안녕하세요 반갑습니다',
        segments: [
          TranscriptionSegment(
            startTime: Duration(seconds: 0),
            endTime: Duration(seconds: 5),
            text: '안녕하세요',
          ),
          TranscriptionSegment(
            startTime: Duration(seconds: 5),
            endTime: Duration(seconds: 10),
            text: '반갑습니다',
          ),
        ],
        language: 'ko',
        processingDuration: Duration(seconds: 3),
      );

      expect(result.offline, isTrue);
      expect(result.engineInfo, 'whisper-base-coreml');
      expect(result.text, '안녕하세요 반갑습니다');
      expect(result.segments.length, 2);
      expect(result.language, 'ko');
      expect(result.processingDuration, Duration(seconds: 3));
    });

    test('creates online result using factory constructor', () {
      final result = TranscriptionResult.online(
        text: '안녕하세요 반갑습니다',
        segments: [
          TranscriptionSegment(
            startTime: Duration(seconds: 0),
            endTime: Duration(seconds: 5),
            text: '안녕하세요',
          ),
        ],
        language: 'ko',
        processingDuration: Duration(seconds: 2),
      );

      expect(result.offline, isFalse);
      expect(result.engineInfo, 'whisper-large-v3-mlx');
      expect(result.text, '안녕하세요 반갑습니다');
    });

    test('creates result with all fields', () {
      final result = TranscriptionResult(
        text: '테스트',
        segments: [
          TranscriptionSegment(
            startTime: Duration(seconds: 0),
            endTime: Duration(seconds: 1),
            text: '테스트',
          ),
        ],
        language: 'ko',
        offline: true,
        createdAt: DateTime.utc(2026, 1, 1),
        processingDuration: Duration(seconds: 1),
        engineInfo: 'whisper-base-coreml',
      );

      expect(result.text, '테스트');
      expect(result.offline, isTrue);
      expect(result.engineInfo, 'whisper-base-coreml');
      expect(result.createdAt, DateTime.utc(2026, 1, 1));
    });

    test('copyWith updates specified fields', () {
      final original = TranscriptionResult.offline(
        text: '원본',
        segments: [
          TranscriptionSegment(
            startTime: Duration(seconds: 0),
            endTime: Duration(seconds: 1),
            text: '원본',
          ),
        ],
        language: 'ko',
      );

      final updated = original.copyWith(
        text: '수정됨',
        processingDuration: Duration(seconds: 5),
      );

      expect(updated.text, '수정됨');
      expect(updated.offline, original.offline);
      expect(updated.processingDuration, Duration(seconds: 5));
    });

    test('fromJson creates offline result from JSON', () {
      final json = {
        'text': '안녕하세요',
        'segments': [
          {
            'start_time': 0,
            'end_time': 5000,
            'text': '안녕하세요',
            'speaker': 'SPEAKER_1',
          }
        ],
        'language': 'ko',
        'offline': true,
        'created_at': '2026-01-01T00:00:00.000Z',
        'processing_duration': 3000,
        'engine_info': 'whisper-base-coreml',
      };

      final result = TranscriptionResult.fromJson(json);

      expect(result.text, '안녕하세요');
      expect(result.offline, isTrue);
      expect(result.engineInfo, 'whisper-base-coreml');
      expect(result.segments.length, 1);
      expect(result.segments[0].text, '안녕하세요');
    });

    test('fromJson creates online result from JSON', () {
      final json = {
        'text': '반갑습니다',
        'segments': [
          {
            'start_time': 5000,
            'end_time': 10000,
            'text': '반갑습니다',
          }
        ],
        'language': 'ko',
        'offline': false,
        'created_at': '2026-01-01T00:00:00.000Z',
        'processing_duration': 2000,
        'engine_info': 'whisper-large-v3-mlx',
      };

      final result = TranscriptionResult.fromJson(json);

      expect(result.text, '반갑습니다');
      expect(result.offline, isFalse);
      expect(result.engineInfo, 'whisper-large-v3-mlx');
    });

    test('toJson serializes offline result to JSON', () {
      final result = TranscriptionResult.offline(
        text: '안녕하세요',
        segments: [
          TranscriptionSegment(
            startTime: Duration(milliseconds: 0),
            endTime: Duration(milliseconds: 5000),
            text: '안녕하세요',
            speaker: 'SPEAKER_1',
          ),
        ],
        language: 'ko',
        createdAt: DateTime.utc(2026, 1, 1),
        processingDuration: Duration(seconds: 3),
      );

      final json = result.toJson();

      expect(json['text'], '안녕하세요');
      expect(json['offline'], isTrue);
      expect(json['engine_info'], 'whisper-base-coreml');
      expect(json['language'], 'ko');
      expect(json['processing_duration'], 3000);
    });

    test('toJson serializes online result to JSON', () {
      final result = TranscriptionResult.online(
        text: '반갑습니다',
        segments: [
          TranscriptionSegment(
            startTime: Duration(milliseconds: 5000),
            endTime: Duration(milliseconds: 10000),
            text: '반갑습니다',
          ),
        ],
        language: 'ko',
        createdAt: DateTime.utc(2026, 1, 1),
        processingDuration: Duration(seconds: 2),
      );

      final json = result.toJson();

      expect(json['text'], '반갑습니다');
      expect(json['offline'], isFalse);
      expect(json['engine_info'], 'whisper-large-v3-mlx');
    });

    test('JSON round-trip preserves data', () {
      final original = TranscriptionResult.offline(
        text: '원본',
        segments: [
          TranscriptionSegment(
            startTime: Duration(seconds: 0),
            endTime: Duration(seconds: 5),
            text: '원본',
            speaker: 'SPEAKER_1',
          ),
        ],
        language: 'ko',
        createdAt: DateTime.utc(2026, 1, 1),
        processingDuration: Duration(seconds: 3),
      );

      final json = original.toJson();
      final restored = TranscriptionResult.fromJson(json);

      expect(restored.text, original.text);
      expect(restored.offline, original.offline);
      expect(restored.engineInfo, original.engineInfo);
      expect(restored.segments.length, original.segments.length);
      expect(restored.segments[0].text, original.segments[0].text);
      expect(restored.segments[0].speaker, original.segments[0].speaker);
    });

    test('segments maintain chronological order', () {
      final result = TranscriptionResult.offline(
        text: '세그먼트 테스트',
        segments: [
          TranscriptionSegment(
            startTime: Duration(seconds: 0),
            endTime: Duration(seconds: 3),
            text: '첫째',
          ),
          TranscriptionSegment(
            startTime: Duration(seconds: 3),
            endTime: Duration(seconds: 6),
            text: '둘째',
          ),
          TranscriptionSegment(
            startTime: Duration(seconds: 6),
            endTime: Duration(seconds: 9),
            text: '셋째',
          ),
        ],
        language: 'ko',
      );

      expect(result.segments[0].text, '첫째');
      expect(result.segments[1].text, '둘째');
      expect(result.segments[2].text, '셋째');
    });
  });
}
