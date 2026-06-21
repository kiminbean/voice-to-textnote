import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/translation.dart';

void main() {
  group('TranslationResult', () {
    test('parses backend translation payload', () {
      final result = TranslationResult.fromJson({
        'task_id': 'sum-001',
        'source_type': 'summary',
        'source_language': 'ko',
        'target_language': 'en',
        'translated_text': 'Meeting summary',
        'source_excerpt': '회의 요약',
        'cached': true,
        'created_at': '2026-06-21T00:00:00+00:00',
      });

      expect(result.taskId, 'sum-001');
      expect(result.sourceType, 'summary');
      expect(result.sourceLanguage, 'ko');
      expect(result.targetLanguage, 'en');
      expect(result.translatedText, 'Meeting summary');
      expect(result.sourceExcerpt, '회의 요약');
      expect(result.cached, isTrue);
    });

    test('uses defensive defaults for sparse payloads', () {
      final result = TranslationResult.fromJson({});

      expect(result.taskId, '');
      expect(result.sourceType, 'auto');
      expect(result.sourceLanguage, isNull);
      expect(result.targetLanguage, '');
      expect(result.translatedText, '');
      expect(result.sourceExcerpt, '');
      expect(result.cached, isFalse);
      expect(result.createdAt, '');
    });
  });
}
