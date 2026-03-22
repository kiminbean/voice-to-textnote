// ResultProvider 테스트 - SPEC-APP-003 REQ-APP-031
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/action_item.dart';
import 'package:voice_to_textnote/providers/result_provider.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';

class MockMinutesApi extends Mock implements MinutesApi {}
class MockSummaryApi extends Mock implements SummaryApi {}

void main() {
  late MockMinutesApi mockMinApi;
  late MockSummaryApi mockSumApi;
  late ProviderContainer container;

  setUp(() {
    mockMinApi = MockMinutesApi();
    mockSumApi = MockSummaryApi();

    container = ProviderContainer(
      overrides: [
        minutesApiProvider.overrideWithValue(mockMinApi),
        summaryApiProvider.overrideWithValue(mockSumApi),
      ],
    );
  });

  tearDown(() {
    container.dispose();
  });

  group('ResultProvider', () {
    // 로딩 초기 상태 테스트
    test('초기 상태는 loading이어야 함', () async {
      // Arrange: 느린 응답 시뮬레이션
      when(() => mockMinApi.getResult(any())).thenAnswer(
        (_) async {
          await Future.delayed(const Duration(seconds: 10));
          return {'minutes': '회의록'};
        },
      );
      when(() => mockSumApi.getResult(any())).thenAnswer(
        (_) async => {
          'summary': '요약',
          'action_items': <dynamic>[],
        },
      );

      // Act
      final state = container.read(resultProvider('task-001'));

      // Assert: 초기는 loading
      expect(state, isA<AsyncLoading>());
    });

    // 성공 상태 테스트 - 구조화된 액션 아이템 파싱 확인
    test('API 성공 시 구조화된 ActionItem 목록을 반환해야 함', () async {
      // Arrange: 백엔드에서 반환하는 구조화된 형식 사용
      when(() => mockMinApi.getResult(any())).thenAnswer((_) async => {
            'minutes': '회의록 내용입니다',
          });
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': 'AI 요약 내용',
            'action_items': [
              {
                'assignee': '김철수',
                'task': '디자인 검토',
                'deadline': '2026-03-25',
                'priority': 'high',
              },
              {
                'task': '코드 리뷰',
              },
            ],
          });

      // Act
      await container.read(resultProvider('task-001').future);
      final state = container.read(resultProvider('task-001'));

      // Assert
      expect(state, isA<AsyncData>());
      final data = state.value!;
      expect(data.minutes, '회의록 내용입니다');
      expect(data.summary, 'AI 요약 내용');
      expect(data.actionItems, hasLength(2));
      // 첫 번째 아이템: 모든 필드 포함
      expect(data.actionItems[0], isA<ActionItem>());
      expect(data.actionItems[0].assignee, '김철수');
      expect(data.actionItems[0].task, '디자인 검토');
      expect(data.actionItems[0].deadline, '2026-03-25');
      expect(data.actionItems[0].priority, 'high');
      // 두 번째 아이템: task만 있어 priority 기본값 medium
      expect(data.actionItems[1].task, '코드 리뷰');
      expect(data.actionItems[1].priority, 'medium');
    });

    // 빈 action_items 처리 테스트
    test('action_items가 빈 배열이면 빈 목록을 반환해야 함', () async {
      // Arrange
      when(() => mockMinApi.getResult(any())).thenAnswer((_) async => {
            'minutes': '회의록 내용',
          });
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': <dynamic>[],
          });

      // Act
      await container.read(resultProvider('task-002').future);
      final state = container.read(resultProvider('task-002'));

      // Assert
      expect(state, isA<AsyncData>());
      expect(state.value!.actionItems, isEmpty);
    });

    // null action_items 처리 테스트
    test('action_items가 null이면 빈 목록을 반환해야 함', () async {
      // Arrange
      when(() => mockMinApi.getResult(any())).thenAnswer((_) async => {
            'minutes': '회의록 내용',
          });
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            // action_items 키 없음 (null과 동일하게 처리)
          });

      // Act
      await container.read(resultProvider('task-003').future);
      final state = container.read(resultProvider('task-003'));

      // Assert
      expect(state, isA<AsyncData>());
      expect(state.value!.actionItems, isEmpty);
    });

    // 잘못된 형식의 action_items graceful 처리 테스트
    test('action_items에 Map이 아닌 항목이 있으면 해당 항목을 무시해야 함', () async {
      // Arrange: 문자열이 섞인 잘못된 형식
      when(() => mockMinApi.getResult(any())).thenAnswer((_) async => {
            'minutes': '회의록',
          });
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              '잘못된 문자열 형식',
              {'task': '올바른 형식'},
              42,
            ],
          });

      // Act
      await container.read(resultProvider('task-004').future);
      final state = container.read(resultProvider('task-004'));

      // Assert: Map 형식인 항목만 파싱, 나머지 무시
      expect(state, isA<AsyncData>());
      expect(state.value!.actionItems, hasLength(1));
      expect(state.value!.actionItems[0].task, '올바른 형식');
    });

    // 실패 상태 테스트
    test('API 실패 시 error 상태를 반환해야 함', () async {
      // Arrange
      when(() => mockMinApi.getResult(any())).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: ''),
          message: '네트워크 오류',
        ),
      );
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': <dynamic>[],
          });

      // Act: 오류 무시하고 상태만 확인
      try {
        await container.read(resultProvider('task-001').future);
      } catch (_) {
        // 예외는 무시
      }
      final state = container.read(resultProvider('task-001'));

      // Assert
      expect(state, isA<AsyncError>());
    });
  });
}
