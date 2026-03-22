// 양식(Template) 데이터 모델 - SPEC-TMPL-001 REQ-TMPL-005
class Template {
  // 백엔드 API의 template_id 필드
  final String templateId;

  // 파일 원본 이름 (표시용)
  final String name;

  // 파일 형식: 'pdf' 또는 'docx'
  final String format;

  // 양식 구조 정보 (상세 조회 시에만 포함)
  final Map<String, dynamic>? structure;

  // 업로드 일시
  final DateTime createdAt;

  const Template({
    required this.templateId,
    required this.name,
    required this.format,
    this.structure,
    required this.createdAt,
  });

  // 특정 필드만 변경한 복사본 반환
  Template copyWith({
    String? templateId,
    String? name,
    String? format,
    Map<String, dynamic>? structure,
    DateTime? createdAt,
  }) {
    return Template(
      templateId: templateId ?? this.templateId,
      name: name ?? this.name,
      format: format ?? this.format,
      structure: structure ?? this.structure,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  // JSON에서 Template 객체 생성
  factory Template.fromJson(Map<String, dynamic> json) {
    return Template(
      templateId: json['template_id'] as String,
      name: json['name'] as String,
      format: json['format'] as String,
      structure: json['structure'] as Map<String, dynamic>?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  // Template 객체를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'template_id': templateId,
      'name': name,
      'format': format,
      'structure': structure,
      'created_at': createdAt.toIso8601String(),
    };
  }
}
