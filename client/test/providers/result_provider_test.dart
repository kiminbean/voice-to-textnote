// ResultProvider 테스트
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
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

    // 성공 상태 테스트
    test('API 성공 시 data 상태를 반환해야 함', () async {
      // Arrange
      when(() => mockMinApi.getResult(any())).thenAnswer((_) async => {
            'minutes': '회의록 내용입니다',
          });
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': 'AI 요약 내용',
            'action_items': ['항목 1', '항목 2'],
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
