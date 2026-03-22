// 액션 아이템 데이터 모델 - SPEC-APP-003 REQ-APP-030
// 백엔드 API에서 반환하는 구조화된 액션 아이템을 표현

// @MX:ANCHOR: ActionItem 모델은 result_provider, result_screen에서 모두 사용
// @MX:REASON: 백엔드 스키마와 직결되는 핵심 데이터 계약

class ActionItem {
  // 담당자 (없을 수 있음)
  final String? assignee;

  // 작업 내용 (필수)
  final String task;

  // 마감일 (자유 형식, 없을 수 있음)
  final String? deadline;

  // 우선순위 (low/medium/high, 기본값: medium)
  final String priority;

  const ActionItem({
    this.assignee,
    required this.task,
    this.deadline,
    this.priority = 'medium',
  });

  // JSON 맵에서 ActionItem 객체 생성
  // 누락된 필드에 대해 graceful하게 기본값 적용
  factory ActionItem.fromJson(Map<String, dynamic> json) {
    return ActionItem(
      assignee: json['assignee'] as String?,
      task: json['task'] as String? ?? '',
      deadline: json['deadline'] as String?,
      priority: json['priority'] as String? ?? 'medium',
    );
  }

  // ActionItem 객체를 JSON 맵으로 변환
  Map<String, dynamic> toJson() {
    return {
      'assignee': assignee,
      'task': task,
      'deadline': deadline,
      'priority': priority,
    };
  }
}
