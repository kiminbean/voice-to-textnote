// SearchApi 서비스 테스트 - SPEC-SEARCH-001
// SearchResponse, SearchResultItem 모델 직렬화 테스트
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/search_result.dart';

void main() {
  group('SearchResultItem', () {
    // fromJson: 기본 직렬화 테스트
    test('fromJson이 JSON을 SearchResultItem으로 변환해야 함', () {
      // Arrange
      final json = {
        'task_id': 'task-123',
        'task_type': 'minutes',
        'snippet': '회의록 내용',
        'created_at': '2024-01-15T10:00:00Z',
        'completed_at': '2024-01-15T10:05:00Z',
      };

      // Act
      final result = SearchResultItem.fromJson(json);

      // Assert
      expect(result.taskId, 'task-123');
      expect(result.taskType, 'minutes');
      expect(result.snippet, '회의록 내용');
      expect(result.createdAt, DateTime.parse('2024-01-15T10:00:00Z'));
      expect(result.completedAt, DateTime.parse('2024-01-15T10:05:00Z'));
    });

    // fromJson: nullable 필드 테스트
    test('fromJson이 null 필드를 올바르게 처리해야 함', () {
      // Arrange
      final json = {
        'task_id': 'task-456',
        'task_type': 'summary',
        'snippet': '<b>강조</b> 내용',
        'created_at': '2024-01-15T10:00:00Z',
        'completed_at': null,
      };

      // Act
      final result = SearchResultItem.fromJson(json);

      // Assert
      expect(result.taskId, 'task-456');
      expect(result.taskType, 'summary');
      expect(result.snippet, '<b>강조</b> 내용');
      expect(result.createdAt, isNotNull);
      expect(result.completedAt, isNull);
    });

    // fromJson: 빈 snippet 기본값 테스트
    test('fromJson이 빈 snippet일 때 빈 문자열을 반환해야 함', () {
      // Arrange
      final json = {
        'task_id': 'task-789',
        'task_type': 'minutes',
        'snippet': null,
        'created_at': '2024-01-15T10:00:00Z',
        'completed_at': null,
      };

      // Act
      final result = SearchResultItem.fromJson(json);

      // Assert
      expect(result.snippet, '');
    });

    // toJson: 직렬화 테스트
    test('toJson이 SearchResultItem을 JSON으로 변환해야 함', () {
      // Arrange
      final item = SearchResultItem(
        taskId: 'task-123',
        taskType: 'minutes',
        snippet: '회의록 내용',
        createdAt: DateTime.parse('2024-01-15T10:00:00Z'),
        completedAt: DateTime.parse('2024-01-15T10:05:00Z'),
      );

      // Act
      final json = item.toJson();

      // Assert
      expect(json['task_id'], 'task-123');
      expect(json['task_type'], 'minutes');
      expect(json['snippet'], '회의록 내용');
      expect(json['created_at'], '2024-01-15T10:00:00.000Z');
      expect(json['completed_at'], '2024-01-15T10:05:00.000Z');
    });
  });

  group('SearchResponse', () {
    // fromJson: 기본 직렬화 테스트
    test('fromJson이 JSON을 SearchResponse로 변환해야 함', () {
      // Arrange
      final json = {
        'items': [
          {
            'task_id': 'task-001',
            'task_type': 'minutes',
            'snippet': '첫 번째 결과',
            'created_at': '2024-01-15T10:00:00Z',
            'completed_at': '2024-01-15T10:05:00Z',
          },
          {
            'task_id': 'task-002',
            'task_type': 'summary',
            'snippet': '두 번째 결과',
            'created_at': '2024-01-15T11:00:00Z',
            'completed_at': '2024-01-15T11:05:00Z',
          },
        ],
        'total': 2,
        'page': 1,
        'page_size': 20,
        'query': '검색어',
      };

      // Act
      final result = SearchResponse.fromJson(json);

      // Assert
      expect(result.items, hasLength(2));
      expect(result.total, 2);
      expect(result.page, 1);
      expect(result.pageSize, 20);
      expect(result.query, '검색어');
      expect(result.items[0].taskId, 'task-001');
      expect(result.items[1].taskId, 'task-002');
    });

    // fromJson: 빈 결과 테스트
    test('fromJson이 빈 결과를 올바르게 처리해야 함', () {
      // Arrange
      final json = {
        'items': <dynamic>[],
        'total': 0,
        'page': 1,
        'page_size': 20,
        'query': '없는 결과',
      };

      // Act
      final result = SearchResponse.fromJson(json);

      // Assert
      expect(result.items, isEmpty);
      expect(result.total, 0);
      expect(result.page, 1);
      expect(result.pageSize, 20);
      expect(result.query, '없는 결과');
    });

    // fromJson: 기본값 테스트
    test('fromJson이 누락된 필드를 기본값으로 처리해야 함', () {
      // Arrange
      final json = {
        'items': [
          {
            'task_id': 'task-001',
            'task_type': 'minutes',
            'snippet': '결과',
            'created_at': '2024-01-15T10:00:00Z',
            'completed_at': '2024-01-15T10:05:00Z',
          },
        ],
        // total, page, pageSize, query 누락
      };

      // Act
      final result = SearchResponse.fromJson(json);

      // Assert
      expect(result.total, 0); // 기본값
      expect(result.page, 1); // 기본값
      expect(result.pageSize, 20); // 기본값
      expect(result.query, ''); // 기본값
    });

    // toJson: 직렬화 테스트
    test('toJson이 SearchResponse를 JSON으로 변환해야 함', () {
      // Arrange
      final response = SearchResponse(
        items: [
          SearchResultItem(
            taskId: 'task-001',
            taskType: 'minutes',
            snippet: '결과',
            createdAt: DateTime.parse('2024-01-15T10:00:00Z'),
            completedAt: null,
          ),
        ],
        total: 1,
        page: 1,
        pageSize: 20,
        query: '검색어',
      );

      // Act
      final json = response.toJson();

      // Assert
      expect(json['items'], hasLength(1));
      expect(json['total'], 1);
      expect(json['page'], 1);
      expect(json['page_size'], 20);
      expect(json['query'], '검색어');
    });

    // totalPages 계산 테스트
    test('totalPages가 올바르게 계산되어야 함', () {
      // Arrange
      final response = SearchResponse(
        items: [],
        total: 45,
        page: 1,
        pageSize: 20,
        query: '검색어',
      );

      // Act & Assert
      expect(response.totalPages, 3); // 45 / 20 = 2.25 → ceil = 3
    });

    // isFirstPage 테스트
    test('isFirstPage가 첫 페이지를 올바르게 식별해야 함', () {
      // Arrange
      final firstPage = SearchResponse(
        items: [],
        total: 10,
        page: 1,
        pageSize: 20,
        query: '검색어',
      );

      final secondPage = SearchResponse(
        items: [],
        total: 10,
        page: 2,
        pageSize: 20,
        query: '검색어',
      );

      // Act & Assert
      expect(firstPage.isFirstPage, true);
      expect(secondPage.isFirstPage, false);
    });

    // isLastPage 테스트
    test('isLastPage가 마지막 페이지를 올바르게 식별해야 함', () {
      // Arrange
      final response = SearchResponse(
        items: [],
        total: 45,
        page: 3,
        pageSize: 20,
        query: '검색어',
      );

      // Act & Assert
      expect(response.isLastPage, true); // 3페이지 == totalPages(3)
    });
  });
}
