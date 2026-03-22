// ActionItem 모델 테스트 - SPEC-APP-003 REQ-APP-030
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/action_item.dart';

void main() {
  group('ActionItem 모델', () {
    // 전체 필드로 fromJson 파싱 테스트
    test('전체 필드를 포함한 JSON에서 올바르게 파싱해야 함', () {
      // Arrange
      final json = {
        'assignee': '김철수',
        'task': '디자인 검토',
        'deadline': '2026-03-25',
        'priority': 'high',
      };

      // Act
      final item = ActionItem.fromJson(json);

      // Assert
      expect(item.assignee, '김철수');
      expect(item.task, '디자인 검토');
      expect(item.deadline, '2026-03-25');
      expect(item.priority, 'high');
    });

    // assignee null인 경우 테스트
    test('assignee가 null인 JSON에서 올바르게 파싱해야 함', () {
      // Arrange
      final json = {
        'assignee': null,
        'task': '코드 리뷰',
        'deadline': '2026-03-30',
        'priority': 'medium',
      };

      // Act
      final item = ActionItem.fromJson(json);

      // Assert
      expect(item.assignee, isNull);
      expect(item.task, '코드 리뷰');
      expect(item.deadline, '2026-03-30');
      expect(item.priority, 'medium');
    });

    // deadline null인 경우 테스트
    test('deadline이 null인 JSON에서 올바르게 파싱해야 함', () {
      // Arrange
      final json = {
        'assignee': '이영희',
        'task': '테스트 작성',
        'deadline': null,
        'priority': 'low',
      };

      // Act
      final item = ActionItem.fromJson(json);

      // Assert
      expect(item.assignee, '이영희');
      expect(item.task, '테스트 작성');
      expect(item.deadline, isNull);
      expect(item.priority, 'low');
    });

    // 빈 객체에서 기본값 테스트 (priority 기본값 = "medium")
    test('task만 있는 JSON에서 priority 기본값 medium이 적용되어야 함', () {
      // Arrange
      final json = {
        'task': '문서 업데이트',
      };

      // Act
      final item = ActionItem.fromJson(json);

      // Assert
      expect(item.task, '문서 업데이트');
      expect(item.assignee, isNull);
      expect(item.deadline, isNull);
      expect(item.priority, 'medium');
    });

    // 빈 JSON 객체에서 graceful handling 테스트
    test('빈 JSON 객체에서 graceful하게 처리해야 함', () {
      // Arrange
      final json = <String, dynamic>{};

      // Act
      final item = ActionItem.fromJson(json);

      // Assert: task는 빈 문자열, priority는 기본값 medium
      expect(item.task, '');
      expect(item.assignee, isNull);
      expect(item.deadline, isNull);
      expect(item.priority, 'medium');
    });

    // toJson 직렬화 테스트
    test('toJson이 올바르게 동작해야 함', () {
      // Arrange
      const item = ActionItem(
        assignee: '박지민',
        task: '배포 준비',
        deadline: '2026-04-01',
        priority: 'high',
      );

      // Act
      final json = item.toJson();

      // Assert
      expect(json['assignee'], '박지민');
      expect(json['task'], '배포 준비');
      expect(json['deadline'], '2026-04-01');
      expect(json['priority'], 'high');
    });

    // null 필드 포함 toJson 테스트
    test('null 필드가 있을 때 toJson이 올바르게 동작해야 함', () {
      // Arrange
      const item = ActionItem(
        assignee: null,
        task: '리뷰 작성',
        deadline: null,
        priority: 'low',
      );

      // Act
      final json = item.toJson();

      // Assert
      expect(json['assignee'], isNull);
      expect(json['task'], '리뷰 작성');
      expect(json['deadline'], isNull);
      expect(json['priority'], 'low');
    });
  });
}
