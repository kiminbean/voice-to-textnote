// SearchResult 모델 테스트 (SPEC-SEARCH-001)
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/search_result.dart';

void main() {
  group('SearchResultItem 모델', () {
    // completedAt 있는 경우 fromJson 테스트
    test('completedAt 포함된 JSON을 올바르게 파싱해야 함', () {
      final json = {
        'task_id': 'uuid-test-001',
        'task_type': 'minutes',
        'snippet': '안녕하세요 <b>검색어</b> 입니다',
        'created_at': '2026-03-22T10:00:00',
        'completed_at': '2026-03-22T10:05:00',
      };

      final item = SearchResultItem.fromJson(json);

      expect(item.taskId, 'uuid-test-001');
      expect(item.taskType, 'minutes');
      expect(item.snippet, '안녕하세요 <b>검색어</b> 입니다');
      expect(item.createdAt, DateTime.parse('2026-03-22T10:00:00'));
      expect(item.completedAt, DateTime.parse('2026-03-22T10:05:00'));
    });

    // completedAt이 null인 경우 fromJson 테스트
    test('completedAt이 null일 때 올바르게 파싱해야 함', () {
      final json = {
        'task_id': 'uuid-test-002',
        'task_type': 'summary',
        'snippet': '요약 <b>키워드</b> 내용',
        'created_at': '2026-03-22T09:00:00',
        'completed_at': null,
      };

      final item = SearchResultItem.fromJson(json);

      expect(item.taskId, 'uuid-test-002');
      expect(item.taskType, 'summary');
      expect(item.completedAt, isNull);
    });

    // completed_at 키가 없는 경우 (필드 누락)
    test('completed_at 키가 없을 때 null로 처리해야 함', () {
      final json = {
        'task_id': 'uuid-test-003',
        'task_type': 'minutes',
        'snippet': '텍스트',
        'created_at': '2026-03-22T08:00:00',
      };

      // completed_at 없이도 정상 파싱
      final item = SearchResultItem.fromJson(json);
      expect(item.completedAt, isNull);
    });
  });

  group('SearchResponse 모델', () {
    // 전체 응답 파싱 테스트
    test('전체 SearchResponse를 올바르게 파싱해야 함', () {
      final json = {
        'items': [
          {
            'task_id': 'uuid-001',
            'task_type': 'minutes',
            'snippet': '첫 번째 <b>결과</b>',
            'created_at': '2026-03-22T10:00:00',
            'completed_at': '2026-03-22T10:05:00',
          },
          {
            'task_id': 'uuid-002',
            'task_type': 'summary',
            'snippet': '두 번째 결과',
            'created_at': '2026-03-21T09:00:00',
            'completed_at': null,
          },
        ],
        'total': 25,
        'page': 1,
        'page_size': 20,
        'query': '검색어',
      };

      final response = SearchResponse.fromJson(json);

      expect(response.total, 25);
      expect(response.page, 1);
      expect(response.pageSize, 20);
      expect(response.query, '검색어');
      expect(response.items.length, 2);
      expect(response.items[0].taskId, 'uuid-001');
      expect(response.items[1].taskType, 'summary');
    });

    // 빈 결과 파싱 테스트
    test('빈 items 목록을 올바르게 파싱해야 함', () {
      final json = {
        'items': <dynamic>[],
        'total': 0,
        'page': 1,
        'page_size': 20,
        'query': '없는검색어',
      };

      final response = SearchResponse.fromJson(json);

      expect(response.items, isEmpty);
      expect(response.total, 0);
    });
  });
}
