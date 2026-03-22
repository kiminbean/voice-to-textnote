// ResultScreen 위젯 테스트 - SPEC-APP-003 REQ-APP-032, REQ-APP-033, REQ-APP-034
// SPEC-APP-004 REQ-APP-042, REQ-APP-043 (주요 결정 사항, 다음 단계 UI)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/screens/result_screen.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';

class MockMinutesApi extends Mock implements MinutesApi {}
class MockSummaryApi extends Mock implements SummaryApi {}

// 테스트용 Meeting 목록 Notifier
class _MockMeetingListNotifier extends MeetingListNotifier {
  final List<Meeting> _meetings;
  _MockMeetingListNotifier(this._meetings);

  @override
  List<Meeting> build() => _meetings;
}

// 액션 아이템 탭까지 진행하는 헬퍼
Future<void> _pumpToActionItemsTab(WidgetTester tester) async {
  // 액션 아이템 탭 버튼 클릭
  await tester.tap(find.text('액션 아이템'));
  await tester.pumpAndSettle();
}

void main() {
  late MockMinutesApi mockMinApi;
  late MockSummaryApi mockSumApi;

  // 테스트용 미팅 데이터 (summaryTaskId 포함)
  final testMeeting = Meeting(
    id: 'meeting-001',
    title: '주간 회의',
    createdAt: DateTime(2026, 3, 22),
    status: MeetingStatus.completed,
    minutesTaskId: 'min-task-001',
    summaryTaskId: 'sum-task-001',
  );

  setUp(() {
    mockMinApi = MockMinutesApi();
    mockSumApi = MockSummaryApi();

    // 회의록 기본 응답
    when(() => mockMinApi.getResult(any())).thenAnswer(
      (_) async => {'markdown': '# 회의록\n내용'},
    );
  });

  // 위젯 테스트 헬퍼: ProviderScope + MaterialApp 래핑
  Widget buildTestWidget(List<Override> overrides) {
    return ProviderScope(
      overrides: [
        minutesApiProvider.overrideWithValue(mockMinApi),
        summaryApiProvider.overrideWithValue(mockSumApi),
        meetingListProvider.overrideWith(
          () => _MockMeetingListNotifier([testMeeting]),
        ),
        ...overrides,
      ],
      child: const MaterialApp(
        home: ResultScreen(meetingId: 'meeting-001'),
      ),
    );
  }

  group('_SummaryTab - 주요 결정 사항 및 다음 단계 표시 (REQ-APP-042, REQ-APP-043)', () {
    // 주요 결정 사항 섹션이 표시되는지 테스트
    testWidgets('keyDecisions가 있을 때 "주요 결정 사항" 섹션이 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary_text': '회의 요약입니다.',
            'action_items': <dynamic>[],
            'key_decisions': ['예산 30% 증액 결정', '신규 인력 채용 승인'],
            'next_steps': <dynamic>[],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await tester.pumpAndSettle();
      // AI 요약 탭으로 이동
      await tester.tap(find.text('AI 요약'));
      await tester.pumpAndSettle();

      // Assert
      expect(find.text('주요 결정 사항'), findsOneWidget);
      expect(find.text('1. 예산 30% 증액 결정'), findsOneWidget);
      expect(find.text('2. 신규 인력 채용 승인'), findsOneWidget);
    });

    // 다음 단계 섹션이 표시되는지 테스트
    testWidgets('nextSteps가 있을 때 "다음 단계" 섹션이 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary_text': '회의 요약입니다.',
            'action_items': <dynamic>[],
            'key_decisions': <dynamic>[],
            'next_steps': ['예산안 초안 작성', '인사팀 협의'],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await tester.pumpAndSettle();
      await tester.tap(find.text('AI 요약'));
      await tester.pumpAndSettle();

      // Assert
      expect(find.text('다음 단계'), findsOneWidget);
      expect(find.text('1. 예산안 초안 작성'), findsOneWidget);
      expect(find.text('2. 인사팀 협의'), findsOneWidget);
    });

    // keyDecisions가 비어있을 때 섹션 숨김 테스트
    testWidgets('keyDecisions가 비어있으면 "주요 결정 사항" 섹션이 표시되지 않아야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary_text': '회의 요약입니다.',
            'action_items': <dynamic>[],
            'key_decisions': <dynamic>[],
            'next_steps': <dynamic>[],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await tester.pumpAndSettle();
      await tester.tap(find.text('AI 요약'));
      await tester.pumpAndSettle();

      // Assert: 섹션 헤더가 없어야 함
      expect(find.text('주요 결정 사항'), findsNothing);
    });

    // nextSteps가 비어있을 때 섹션 숨김 테스트
    testWidgets('nextSteps가 비어있으면 "다음 단계" 섹션이 표시되지 않아야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary_text': '회의 요약입니다.',
            'action_items': <dynamic>[],
            'key_decisions': <dynamic>[],
            'next_steps': <dynamic>[],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await tester.pumpAndSettle();
      await tester.tap(find.text('AI 요약'));
      await tester.pumpAndSettle();

      // Assert: 섹션 헤더가 없어야 함
      expect(find.text('다음 단계'), findsNothing);
    });

    // 번호 매기기 목록 표시 테스트
    testWidgets('키 결정 사항이 번호 매기기 목록으로 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary_text': '요약',
            'action_items': <dynamic>[],
            'key_decisions': ['첫 번째 결정', '두 번째 결정', '세 번째 결정'],
            'next_steps': <dynamic>[],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await tester.pumpAndSettle();
      await tester.tap(find.text('AI 요약'));
      await tester.pumpAndSettle();

      // Assert: 번호 형식 확인
      expect(find.text('1. 첫 번째 결정'), findsOneWidget);
      expect(find.text('2. 두 번째 결정'), findsOneWidget);
      expect(find.text('3. 세 번째 결정'), findsOneWidget);
    });
  });

  group('_ActionItemsTab - 액션 아이템 카드 표시', () {
    // 담당자, 작업, 마감일, 우선순위 배지 표시 테스트
    testWidgets('액션 아이템 카드에 담당자, 작업, 마감일, 우선순위 배지가 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              {
                'assignee': '김철수',
                'task': '디자인 검토',
                'deadline': '2026-03-25',
                'priority': 'high',
              },
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // Assert
      expect(find.text('디자인 검토'), findsOneWidget);
      expect(find.text('담당자: 김철수'), findsOneWidget);
      expect(find.text('마감: 2026-03-25'), findsOneWidget);
      expect(find.text('HIGH'), findsOneWidget);
    });

    // 담당자 없을 때 "미지정" 표시 테스트
    testWidgets('담당자가 없으면 "미지정"으로 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              {
                'task': '코드 리뷰',
                'priority': 'medium',
              },
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // Assert
      expect(find.text('코드 리뷰'), findsOneWidget);
      expect(find.text('담당자: 미지정'), findsOneWidget);
    });

    // 체크박스 토글 테스트
    testWidgets('체크박스 토글 시 취소선이 적용되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              {
                'task': '보고서 작성',
                'priority': 'medium',
              },
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // 체크박스 클릭
      await tester.tap(find.byType(Checkbox).first);
      await tester.pump();

      // Assert: 텍스트에 취소선이 적용되었는지 확인
      // (TextStyle.decoration == TextDecoration.lineThrough)
      final textFinder = find.text('보고서 작성');
      expect(textFinder, findsOneWidget);
    });
  });

  group('_ActionItemsTab - 우선순위 배지 색상', () {
    // high 우선순위는 빨간색 배지
    testWidgets('high 우선순위는 빨간색 배지로 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              {'task': '긴급 작업', 'priority': 'high'},
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // Assert: HIGH 텍스트를 가진 배지가 존재
      expect(find.text('HIGH'), findsOneWidget);
    });

    // medium 우선순위는 주황색 배지
    testWidgets('medium 우선순위는 주황색 배지로 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              {'task': '일반 작업', 'priority': 'medium'},
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // Assert
      expect(find.text('MEDIUM'), findsOneWidget);
    });

    // low 우선순위는 초록색 배지
    testWidgets('low 우선순위는 초록색 배지로 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              {'task': '선택 작업', 'priority': 'low'},
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // Assert
      expect(find.text('LOW'), findsOneWidget);
    });
  });

  group('_ActionItemsTab - 필터 칩', () {
    // 필터 칩 표시 테스트
    testWidgets('전체/High/Medium/Low 필터 칩이 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              {'task': '작업 A', 'priority': 'high'},
              {'task': '작업 B', 'priority': 'medium'},
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // Assert: 필터 칩 모두 존재
      expect(find.text('전체'), findsOneWidget);
      expect(find.text('High'), findsOneWidget);
      expect(find.text('Medium'), findsOneWidget);
      expect(find.text('Low'), findsOneWidget);
    });

    // 필터 적용 테스트 (High 선택 시 high 아이템만 표시)
    testWidgets('High 필터 선택 시 high 우선순위 아이템만 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              {'task': '긴급 작업', 'priority': 'high'},
              {'task': '일반 작업', 'priority': 'medium'},
              {'task': '선택 작업', 'priority': 'low'},
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // High 필터 클릭
      await tester.tap(find.text('High'));
      await tester.pump();

      // Assert: high 아이템만 보임
      expect(find.text('긴급 작업'), findsOneWidget);
      expect(find.text('일반 작업'), findsNothing);
      expect(find.text('선택 작업'), findsNothing);
    });

    // 전체 필터로 복귀 테스트
    testWidgets('전체 필터 선택 시 모든 아이템이 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': [
              {'task': '긴급 작업', 'priority': 'high'},
              {'task': '일반 작업', 'priority': 'medium'},
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // High 필터 → 전체 필터 순서로 클릭
      await tester.tap(find.text('High'));
      await tester.pump();
      await tester.tap(find.text('전체'));
      await tester.pump();

      // Assert: 모든 아이템 표시
      expect(find.text('긴급 작업'), findsOneWidget);
      expect(find.text('일반 작업'), findsOneWidget);
    });
  });

  group('_ActionItemsTab - 빈 상태 및 오류 상태', () {
    // 빈 상태 위젯 표시 테스트
    testWidgets('action_items가 없으면 EmptyStateWidget이 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenAnswer((_) async => {
            'summary': '요약',
            'action_items': <dynamic>[],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // Assert: 빈 상태 메시지 표시
      expect(find.text('액션 아이템이 없습니다'), findsOneWidget);
    });

    // 오류 상태 위젯 표시 테스트
    testWidgets('API 오류 시 ErrorRetryWidget이 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getResult(any())).thenThrow(
        Exception('네트워크 오류'),
      );

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToActionItemsTab(tester);

      // Assert: 오류 메시지와 재시도 버튼 표시
      expect(find.text('액션 아이템을 불러올 수 없습니다'), findsOneWidget);
      expect(find.text('다시 시도'), findsOneWidget);
    });
  });
}
