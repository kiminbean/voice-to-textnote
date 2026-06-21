class StudySourceRef {
  final int segmentIndex;
  final String? speaker;
  final double? start;
  final double? end;
  final String text;

  const StudySourceRef({
    required this.segmentIndex,
    this.speaker,
    this.start,
    this.end,
    required this.text,
  });

  factory StudySourceRef.fromJson(Map<String, dynamic> json) => StudySourceRef(
        segmentIndex: json['segment_index'] as int,
        speaker: json['speaker'] as String?,
        start: (json['start'] as num?)?.toDouble(),
        end: (json['end'] as num?)?.toDouble(),
        text: json['text'] as String? ?? '',
      );
}

class StudyKeyConcept {
  final String term;
  final String explanation;
  final List<int> sourceRefs;

  const StudyKeyConcept({
    required this.term,
    required this.explanation,
    this.sourceRefs = const [],
  });

  factory StudyKeyConcept.fromJson(Map<String, dynamic> json) =>
      StudyKeyConcept(
        term: json['term'] as String? ?? '',
        explanation: json['explanation'] as String? ?? '',
        sourceRefs: _parseIntList(json['source_refs']),
      );
}

class StudyFlashcard {
  final String front;
  final String back;
  final List<int> sourceRefs;

  const StudyFlashcard({
    required this.front,
    required this.back,
    this.sourceRefs = const [],
  });

  factory StudyFlashcard.fromJson(Map<String, dynamic> json) => StudyFlashcard(
        front: json['front'] as String? ?? '',
        back: json['back'] as String? ?? '',
        sourceRefs: _parseIntList(json['source_refs']),
      );
}

class StudyQuizQuestion {
  final String question;
  final String answer;
  final String difficulty;
  final List<int> sourceRefs;

  const StudyQuizQuestion({
    required this.question,
    required this.answer,
    required this.difficulty,
    this.sourceRefs = const [],
  });

  factory StudyQuizQuestion.fromJson(Map<String, dynamic> json) =>
      StudyQuizQuestion(
        question: json['question'] as String? ?? '',
        answer: json['answer'] as String? ?? '',
        difficulty: json['difficulty'] as String? ?? 'medium',
        sourceRefs: _parseIntList(json['source_refs']),
      );
}

class StudyPack {
  final String taskId;
  final String mode;
  final String language;
  final List<StudyKeyConcept> keyConcepts;
  final List<StudyFlashcard> flashcards;
  final List<StudyQuizQuestion> quizQuestions;
  final String studyNotes;
  final List<StudySourceRef> sourceRefs;
  final String createdAt;

  const StudyPack({
    required this.taskId,
    required this.mode,
    required this.language,
    required this.keyConcepts,
    required this.flashcards,
    required this.quizQuestions,
    required this.studyNotes,
    required this.sourceRefs,
    required this.createdAt,
  });

  factory StudyPack.fromJson(Map<String, dynamic> json) => StudyPack(
        taskId: json['task_id'] as String? ?? '',
        mode: json['mode'] as String? ?? 'general',
        language: json['language'] as String? ?? 'ko',
        keyConcepts: (json['key_concepts'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(StudyKeyConcept.fromJson)
            .toList(),
        flashcards: (json['flashcards'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(StudyFlashcard.fromJson)
            .toList(),
        quizQuestions: (json['quiz_questions'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(StudyQuizQuestion.fromJson)
            .toList(),
        studyNotes: json['study_notes'] as String? ?? '',
        sourceRefs: (json['source_refs'] as List<dynamic>? ?? [])
            .whereType<Map<String, dynamic>>()
            .map(StudySourceRef.fromJson)
            .toList(),
        createdAt: json['created_at'] as String? ?? '',
      );
}

List<int> _parseIntList(dynamic value) {
  if (value is! List) return [];
  return value
      .where((item) => item is int || item is num)
      .map((item) => (item as num).toInt())
      .toList();
}
