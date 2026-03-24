// AI 요약 결과 데이터 모델 - SPEC-APP-004 REQ-APP-040
// 백엔드 SummaryResponse의 모든 필드를 타입 안전하게 표현
// key_decisions와 next_steps 필드를 포함하여 완전한 요약 데이터 제공

// @MX:ANCHOR: SummaryResult는 summaryResultProvider, _SummaryTab, _ActionItemsTab에서 사용
// @MX:REASON: 백엔드 SummaryResponse 스키마와 직결되는 핵심 데이터 계약 (SPEC-APP-004)

import 'dart:convert';

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

  // REQ-UI-003: 양식 섹션별 내용 (양식 선택 시에만 존재)
  final Map<String, String> sections;

  // REQ-UI-001: 양식 구조 정보 (양식 선택 시에만 존재)
  final Map<String, dynamic>? templateStructure;

  const SummaryResult({
    required this.summaryText,
    required this.actionItems,
    required this.keyDecisions,
    required this.nextSteps,
    this.sections = const {},
    this.templateStructure,
  });

  // JSON 맵에서 SummaryResult 객체 생성
  // 누락된 필드에 대해 graceful하게 기본값 적용
  factory SummaryResult.fromJson(Map<String, dynamic> json) {
    // summary_text 우선, 없으면 summary 키 사용 (하위 호환성)
    var summaryText =
        json['summary_text'] as String? ?? json['summary'] as String? ?? '';

    // 방어 처리: summary_text가 JSON 문자열이면 내부 필드 추출
    var actionItems = <ActionItem>[];
    var keyDecisions = <String>[];
    var nextSteps = <String>[];
    var nestedSections = <String, String>{};

    if (summaryText.trimLeft().startsWith('{')) {
      try {
        // JSON 주석 제거 (OpenAI가 // 주석을 삽입하는 경우)
        var cleanedJson = summaryText.replaceAll(RegExp(r'//[^\n]*'), '');
        // 후행 쉼표 제거 (주석 제거 후 남은 ,} 또는 ,] 패턴)
        cleanedJson = cleanedJson.replaceAll(RegExp(r',\s*([}\]])'), r'$1');
        final nested = jsonDecode(cleanedJson) as Map<String, dynamic>;
        summaryText = nested['summary_text'] as String? ?? summaryText;
        // 중첩 JSON에서 추가 필드도 추출
        if (nested.containsKey('action_items')) {
          actionItems = (nested['action_items'] as List<dynamic>? ?? [])
              .whereType<Map<String, dynamic>>()
              .map((e) => ActionItem.fromJson(e))
              .toList();
        }
        if (nested.containsKey('key_decisions')) {
          keyDecisions = _extractStrings(nested['key_decisions']);
        }
        if (nested.containsKey('next_steps')) {
          nextSteps = _extractStrings(nested['next_steps']);
        }
        // 중첩 JSON에서 sections도 추출
        if (nested.containsKey('sections') && nested['sections'] is Map) {
          for (final entry in (nested['sections'] as Map).entries) {
            nestedSections[entry.key.toString()] = entry.value?.toString() ?? '';
          }
        }
      } catch (_) {
        // JSON 파싱 실패 시 원본 텍스트 유지
      }
    }

    // 기본 필드에서 파싱 (중첩 JSON에서 이미 추출되지 않은 경우)
    if (actionItems.isEmpty) {
      actionItems = (json['action_items'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map((e) => ActionItem.fromJson(e))
          .toList();
    }

    if (keyDecisions.isEmpty) {
      keyDecisions = (json['key_decisions'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList();
    }

    if (nextSteps.isEmpty) {
      nextSteps = (json['next_steps'] as List<dynamic>? ?? [])
          .whereType<String>()
          .toList();
    }

    // REQ-UI-003: sections 파싱 (양식 섹션별 내용)
    // 1순위: 외부 JSON의 sections 필드
    // 2순위: 중첩 JSON에서 추출한 nestedSections
    final rawSections = json['sections'];
    var sections = <String, String>{};
    if (rawSections is Map) {
      for (final entry in rawSections.entries) {
        sections[entry.key.toString()] = entry.value?.toString() ?? '';
      }
    }
    if (sections.isEmpty && nestedSections.isNotEmpty) {
      sections = nestedSections;
    }

    // REQ-UI-001: template_structure 파싱
    final templateStructure = json['template_structure'] as Map<String, dynamic>?;

    return SummaryResult(
      summaryText: summaryText,
      actionItems: actionItems,
      keyDecisions: keyDecisions,
      nextSteps: nextSteps,
      sections: sections,
      templateStructure: templateStructure,
    );
  }

  // 중첩 JSON에서 문자열 목록 추출 (List<String> 또는 List<Map> 형태 모두 처리)
  static List<String> _extractStrings(dynamic value) {
    if (value is! List) return [];
    return value
        .map((e) {
          if (e is String) return e;
          if (e is Map) return e['decision'] as String? ?? e['step'] as String? ?? e.toString();
          return e.toString();
        })
        .cast<String>()
        .toList();
  }
}
