// AI 마인드맵 결과 데이터 모델

class MindMapResult {
  final String taskId;
  final String summaryTaskId;
  final String status;
  final MindMapNode? root;
  final List<MindMapEdge> edges;
  final String? errorMessage;

  const MindMapResult({
    required this.taskId,
    required this.summaryTaskId,
    required this.status,
    required this.root,
    required this.edges,
    this.errorMessage,
  });

  factory MindMapResult.fromJson(Map<String, dynamic> json) {
    return MindMapResult(
      taskId: json['task_id'] as String? ?? '',
      summaryTaskId: json['summary_task_id'] as String? ?? '',
      status: json['status'] as String? ?? 'pending',
      root: json['root'] is Map<String, dynamic>
          ? MindMapNode.fromJson(json['root'] as Map<String, dynamic>)
          : null,
      edges: (json['edges'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(MindMapEdge.fromJson)
          .toList(),
      errorMessage: json['error_message'] as String?,
    );
  }
}

class MindMapNode {
  final String id;
  final String title;
  final String summary;
  final List<MindMapNode> children;
  final List<String> sourceRefs;

  const MindMapNode({
    required this.id,
    required this.title,
    required this.summary,
    required this.children,
    required this.sourceRefs,
  });

  factory MindMapNode.fromJson(Map<String, dynamic> json) {
    return MindMapNode(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      children: (json['children'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(MindMapNode.fromJson)
          .toList(),
      sourceRefs: (json['source_refs'] as List<dynamic>? ?? [])
          .map((value) => value.toString())
          .toList(),
    );
  }
}

class MindMapEdge {
  final String source;
  final String target;
  final String relation;

  const MindMapEdge({
    required this.source,
    required this.target,
    required this.relation,
  });

  factory MindMapEdge.fromJson(Map<String, dynamic> json) {
    return MindMapEdge(
      source: json['source'] as String? ?? '',
      target: json['target'] as String? ?? '',
      relation: json['relation'] as String? ?? 'related_to',
    );
  }
}
