// SummaryResult 모델 테스트 - SPEC-APP-004 REQ-APP-040
// 백엔드 SummaryResponse의 모든 필드를 타입 안전하게 파싱하는지 검증
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/action_item.dart';
import 'package:voice_to_textnote/models/summary_result.dart';

void main() {
  group('SummaryResult.fromJson', () {
    // 모든 필드가 있는 경우 파싱 테스트
    test('모든 필드가 있을 때 올바르게 파싱해야 함', () {
      // Arrange
      final json = {
        'summary_text': '오늘 회의에서 예산 증액을 결정했습니다.',
        'action_items': [
          {
            'assignee': '김철수',
            'task': '예산안 작성',
            'deadline': '2026-04-01',
            'priority': 'high',
          },
        ],
        'key_decisions': ['예산 30% 증액 결정', '신규 인력 채용 승인'],
        'next_steps': ['예산안 초안 작성', '인사팀 협의'],
      };

      // Act
      final result = SummaryResult.fromJson(json);

      // Assert
      expect(result.summaryText, '오늘 회의에서 예산 증액을 결정했습니다.');
      expect(result.actionItems, hasLength(1));
      expect(result.actionItems[0].assignee, '김철수');
      expect(result.actionItems[0].task, '예산안 작성');
      expect(result.keyDecisions, hasLength(2));
      expect(result.keyDecisions[0], '예산 30% 증액 결정');
      expect(result.keyDecisions[1], '신규 인력 채용 승인');
      expect(result.nextSteps, hasLength(2));
      expect(result.nextSteps[0], '예산안 초안 작성');
      expect(result.nextSteps[1], '인사팀 협의');
    });

    // key_decisions와 next_steps가 없는 경우 기본값(빈 목록) 테스트
    test('key_decisions와 next_steps가 없으면 빈 목록을 기본값으로 사용해야 함', () {
      // Arrange: 기존 백엔드가 두 필드를 반환하지 않는 경우
      final json = {
        'summary_text': '요약 내용',
        'action_items': <dynamic>[],
      };

      // Act
      final result = SummaryResult.fromJson(json);

      // Assert
      expect(result.summaryText, '요약 내용');
      expect(result.keyDecisions, isEmpty);
      expect(result.nextSteps, isEmpty);
    });

    // 빈 객체에서 기본값 적용 테스트
    test('빈 JSON 객체에서 모든 필드에 기본값이 적용되어야 함', () {
      // Arrange
      final json = <String, dynamic>{};

      // Act
      final result = SummaryResult.fromJson(json);

      // Assert
      expect(result.summaryText, '');
      expect(result.actionItems, isEmpty);
      expect(result.keyDecisions, isEmpty);
      expect(result.nextSteps, isEmpty);
    });

    // summary 키도 인식하는지 테스트 (하위 호환성)
    test('summary_text 대신 summary 키가 있어도 올바르게 파싱해야 함', () {
      // Arrange: 일부 코드에서 summary 키 사용
      final json = {
        'summary': '구형 키로 반환된 요약',
        'action_items': <dynamic>[],
        'key_decisions': <dynamic>[],
        'next_steps': <dynamic>[],
      };

      // Act
      final result = SummaryResult.fromJson(json);

      // Assert
      expect(result.summaryText, '구형 키로 반환된 요약');
    });

    // ActionItem 중첩 파싱 테스트
    test('action_items 내부의 ActionItem이 올바르게 파싱되어야 함', () {
      // Arrange
      final json = {
        'summary_text': '요약',
        'action_items': [
          {
            'assignee': '이영희',
            'task': '보고서 제출',
            'deadline': '2026-03-31',
            'priority': 'medium',
          },
          {
            'task': '담당자 없는 작업',
            // assignee, deadline 없음
          },
        ],
        'key_decisions': <dynamic>[],
        'next_steps': <dynamic>[],
      };

      // Act
      final result = SummaryResult.fromJson(json);

      // Assert
      expect(result.actionItems, hasLength(2));
      expect(result.actionItems[0], isA<ActionItem>());
      expect(result.actionItems[0].assignee, '이영희');
      expect(result.actionItems[0].priority, 'medium');
      expect(result.actionItems[1].assignee, isNull);
      expect(result.actionItems[1].priority, 'medium'); // 기본값
    });

    // Map이 아닌 action_items 항목은 무시하는지 테스트
    test('action_items에 Map이 아닌 항목이 있으면 해당 항목을 무시해야 함', () {
      // Arrange
      final json = {
        'summary_text': '요약',
        'action_items': [
          '잘못된 문자열',
          {'task': '올바른 형식'},
          42,
        ],
        'key_decisions': <dynamic>[],
        'next_steps': <dynamic>[],
      };

      // Act
      final result = SummaryResult.fromJson(json);

      // Assert: Map 형식인 항목만 파싱
      expect(result.actionItems, hasLength(1));
      expect(result.actionItems[0].task, '올바른 형식');
    });

    // key_decisions에 String이 아닌 항목은 무시하는지 테스트
    test('key_decisions에 String이 아닌 항목이 있으면 무시해야 함', () {
      // Arrange
      final json = {
        'summary_text': '요약',
        'action_items': <dynamic>[],
        'key_decisions': ['유효한 결정', 123, null, '또 다른 결정'],
        'next_steps': <dynamic>[],
      };

      // Act
      final result = SummaryResult.fromJson(json);

      // Assert: String만 포함
      expect(result.keyDecisions, hasLength(2));
      expect(result.keyDecisions[0], '유효한 결정');
      expect(result.keyDecisions[1], '또 다른 결정');
    });
  });
}
