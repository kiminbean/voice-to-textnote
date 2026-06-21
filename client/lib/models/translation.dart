class TranslationResult {
  final String taskId;
  final String sourceType;
  final String? sourceLanguage;
  final String targetLanguage;
  final String translatedText;
  final String sourceExcerpt;
  final bool cached;
  final String createdAt;

  const TranslationResult({
    required this.taskId,
    required this.sourceType,
    required this.sourceLanguage,
    required this.targetLanguage,
    required this.translatedText,
    required this.sourceExcerpt,
    required this.cached,
    required this.createdAt,
  });

  factory TranslationResult.fromJson(Map<String, dynamic> json) =>
      TranslationResult(
        taskId: json['task_id'] as String? ?? '',
        sourceType: json['source_type'] as String? ?? 'auto',
        sourceLanguage: json['source_language'] as String?,
        targetLanguage: json['target_language'] as String? ?? '',
        translatedText: json['translated_text'] as String? ?? '',
        sourceExcerpt: json['source_excerpt'] as String? ?? '',
        cached: json['cached'] as bool? ?? false,
        createdAt: json['created_at'] as String? ?? '',
      );
}
