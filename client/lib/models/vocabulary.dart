class Vocabulary {
  final String id;
  final String name;
  final List<String> words;
  final DateTime createdAt;
  final DateTime updatedAt;

  Vocabulary({
    required this.id,
    required this.name,
    required this.words,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Vocabulary.fromJson(Map<String, dynamic> json) {
    return Vocabulary(
      id: json['id'] as String,
      name: json['name'] as String,
      words: (json['words'] as List<dynamic>).map((e) => e as String).toList(),
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'words': words,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }
}
