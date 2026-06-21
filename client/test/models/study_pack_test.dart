import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/study_pack.dart';

void main() {
  group('StudyPack', () {
    test('fromJson parses grounded study artifacts', () {
      final result = StudyPack.fromJson({
        'task_id': 'min-001',
        'mode': 'lecture',
        'language': 'ko',
        'key_concepts': [
          {
            'term': '광합성',
            'explanation': '빛 에너지 전환',
            'source_refs': [0],
          },
        ],
        'flashcards': [
          {
            'front': '광합성이란?',
            'back': '빛 에너지 전환',
            'source_refs': [0],
          },
        ],
        'quiz_questions': [
          {
            'question': '엽록소의 역할은?',
            'answer': '빛 흡수',
            'difficulty': 'easy',
            'source_refs': [1],
          },
        ],
        'study_notes': '핵심 노트',
        'source_refs': [
          {
            'segment_index': 0,
            'speaker': '교수',
            'start': 12,
            'end': 18.5,
            'text': '광합성 설명',
          },
        ],
        'created_at': '2026-06-21T00:00:00+00:00',
      });

      expect(result.taskId, 'min-001');
      expect(result.mode, 'lecture');
      expect(result.keyConcepts.single.term, '광합성');
      expect(result.flashcards.single.front, '광합성이란?');
      expect(result.quizQuestions.single.difficulty, 'easy');
      expect(result.sourceRefs.single.start, 12.0);
    });

    test('fromJson defaults missing optional collections', () {
      final result = StudyPack.fromJson({'task_id': 'min-001'});

      expect(result.taskId, 'min-001');
      expect(result.mode, 'general');
      expect(result.language, 'ko');
      expect(result.keyConcepts, isEmpty);
      expect(result.flashcards, isEmpty);
      expect(result.quizQuestions, isEmpty);
      expect(result.sourceRefs, isEmpty);
    });
  });
}
