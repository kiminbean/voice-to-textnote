// AI 요약 결과 데이터 모델 - SPEC-APP-004 REQ-APP-040
// 백엔드 SummaryResponse의 모든 필드를 타입 안전하게 표현
// key_decisions와 next_steps 필드를 포함하여 완전한 요약 데이터 제공

// @MX:ANCHOR: SummaryResult는 summaryResultProvider, _SummaryTab, _ActionItemsTab에서 사용
// @MX:REASON: 백엔드 SummaryResponse 스키마와 직결되는 핵심 데이터 계약 (SPEC-APP-004)

import 'package:voice_to_textnote/models/action_item.dart';

class SummaryResult {
  // AI 요약 텍스트 (summary_text 또는 summary 키에서 파싱)
  final String summaryText;

  // 구조화된 액션 아이템 목록
  final List<ActionItem> actionItems;

  // 주요 결정 사항 목록 (SPEC-APP-004 REQ-APP-042)
  final List<String> keyDecisions;

  // 다음 단계 목록 (SPEC-APP-004 REQ-APP-043)
  final List<String> nextSteps;

  const SummaryResult({
    required this.summaryText,
    required this.actionItems,
    required this.keyDecisions,
    required this.nextSteps,
  });

  // JSON 맵에서 SummaryResult 객체 생성
  // 누락된 필드에 대해 graceful하게 기본값 적용
  factory SummaryResult.fromJson(Map<String, dynamic> json) {
    // summary_text 우선, 없으면 summary 키 사용 (하위 호환성)
    final summaryText =
        json['summary_text'] as String? ?? json['summary'] as String? ?? '';

    // action_items: Map 형식인 항목만 파싱, 잘못된 형식은 무시
    final actionItems = (json['action_items'] as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map((e) => ActionItem.fromJson(e))
        .toList();

    // key_decisions: String 형식인 항목만 포함, 잘못된 형식은 무시
    final keyDecisions = (json['key_decisions'] as List<dynamic>? ?? [])
        .whereType<String>()
        .toList();

    // next_steps: String 형식인 항목만 포함, 잘못된 형식은 무시
    final nextSteps = (json['next_steps'] as List<dynamic>? ?? [])
        .whereType<String>()
        .toList();

    return SummaryResult(
      summaryText: summaryText,
      actionItems: actionItems,
      keyDecisions: keyDecisions,
      nextSteps: nextSteps,
    );
  }
}
