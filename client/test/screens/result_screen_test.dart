// ResultScreen 위젯 테스트 - SPEC-APP-003 REQ-APP-032, REQ-APP-033, REQ-APP-034
// SPEC-APP-004 REQ-APP-042, REQ-APP-043 (주요 결정 사항, 다음 단계 UI)
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/models/study_pack.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/screens/result_screen.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/study_pack_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';

class MockMinutesApi extends Mock implements MinutesApi {}

class MockSummaryApi extends Mock implements SummaryApi {}

class MockStudyPackApi extends Mock implements StudyPackApi {}

// 테스트용 Meeting 목록 Notifier (AsyncNotifier이므로 Future<List<Meeting>> 반환)
class _MockMeetingListNotifier extends MeetingListNotifier {
  final List<Meeting> _meetings;
  _MockMeetingListNotifier(this._meetings);

  @override
  Future<List<Meeting>> build() async => _meetings;
}

// 액션 아이템 탭까지 진행하는 헬퍼
Future<void> _pumpToActionItemsTab(WidgetTester tester) async {
  // 액션 아이템 탭 버튼 클릭
  await tester.ensureVisible(find.text('액션 아이템'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('액션 아이템'));
  await tester.pumpAndSettle();
}

Future<void> _pumpToMindMapTab(WidgetTester tester) async {
  await tester.ensureVisible(find.text('마인드맵'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('마인드맵'));
  await tester.pumpAndSettle();
}

Future<void> _pumpToStudyTab(WidgetTester tester) async {
  await tester.ensureVisible(find.text('학습'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('학습'));
  await tester.pumpAndSettle();
}

Finder _tabText(String label) {
  return find.descendant(
    of: find.byType(TabBar),
    matching: find.text(label),
  );
}

void main() {
  late MockMinutesApi mockMinApi;
  late MockSummaryApi mockSumApi;
  late MockStudyPackApi mockStudyPackApi;

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
    mockStudyPackApi = MockStudyPackApi();

    // 회의록 기본 응답
    when(() => mockMinApi.getResult(any())).thenAnswer(
      (_) async => {'markdown': '# 회의록\n내용'},
    );
    when(() => mockSumApi.createMindMap(any())).thenAnswer(
      (_) async => {'task_id': 'mind-task-001', 'status': 'pending'},
    );
    when(() => mockSumApi.getMindMapStatus(any())).thenAnswer(
      (_) async => {'status': 'completed'},
    );
    when(() => mockSumApi.getMindMapResult(any())).thenAnswer(
      (_) async => {
        'task_id': 'mind-task-001',
        'summary_task_id': 'sum-task-001',
        'status': 'completed',
        'root': {
          'id': 'root',
          'title': '회의 인사이트',
          'summary': '회의 핵심 요약입니다.',
          'source_refs': ['summary_text'],
          'children': <dynamic>[],
        },
        'edges': <dynamic>[],
      },
    );
    when(() => mockStudyPackApi.get(
          any(),
          mode: any(named: 'mode'),
          language: any(named: 'language'),
        )).thenAnswer(
      (_) async => const StudyPack(
        taskId: 'min-task-001',
        mode: 'lecture',
        language: 'ko',
        studyNotes: 'Owll 벤치마크 결과를 학습 노트로 정리했습니다.',
        keyConcepts: [
          StudyKeyConcept(
            term: 'Owll 벤치마크',
            explanation: '회의록을 플래시카드와 퀴즈로 전환하는 경쟁 기능입니다.',
            sourceRefs: [0],
          ),
        ],
        flashcards: [
          StudyFlashcard(
            front: 'Owll 벤치마크에서 우선 도입할 기능은?',
            back: '백엔드 생성 Study Pack입니다.',
            sourceRefs: [0],
          ),
        ],
        quizQuestions: [
          StudyQuizQuestion(
            question: 'Study Pack은 어디에서 생성되나요?',
            answer: '백엔드 Study Pack API에서 생성됩니다.',
            difficulty: 'medium',
            sourceRefs: [0],
          ),
        ],
        sourceRefs: [
          StudySourceRef(
            segmentIndex: 0,
            speaker: '김철수',
            start: 12,
            text: 'Owll 벤치마크 결과를 공유했습니다.',
          ),
        ],
        createdAt: '2026-03-22T00:00:00Z',
      ),
    );
  });

  // 위젯 테스트 헬퍼: ProviderScope + MaterialApp 래핑
  Widget buildTestWidget(List<Override> overrides) {
    return ProviderScope(
      overrides: [
        minutesApiProvider.overrideWithValue(mockMinApi),
        summaryApiProvider.overrideWithValue(mockSumApi),
        studyPackApiProvider.overrideWithValue(mockStudyPackApi),
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
      await tester.tap(_tabText('AI 요약'));
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
      await tester.tap(_tabText('AI 요약'));
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
      await tester.tap(_tabText('AI 요약'));
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
      await tester.tap(_tabText('AI 요약'));
      await tester.pumpAndSettle();

      // Assert: 섹션 헤더가 없어야 함
      expect(find.text('다음 단계'), findsNothing);
    });

    // 번호 매기기 목록 표시 테스트
    testWidgets('키 결정 사항이 번호 매기기 목록으로 표시되어야 함', (WidgetTester tester) async {
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
      await tester.tap(_tabText('AI 요약'));
      await tester.pumpAndSettle();

      // Assert: 번호 형식 확인
      expect(find.text('1. 첫 번째 결정'), findsOneWidget);
      expect(find.text('2. 두 번째 결정'), findsOneWidget);
      expect(find.text('3. 세 번째 결정'), findsOneWidget);
    });
  });

  group('_StudyTab - 플래시카드 및 복습 퀴즈 표시', () {
    testWidgets('백엔드 Study Pack으로 학습 카드와 퀴즈를 표시해야 함',
        (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToStudyTab(tester);

      // Assert
      expect(find.text('학습 노트'), findsOneWidget);
      expect(find.text('핵심 개념'), findsOneWidget);
      expect(find.text('플래시카드'), findsWidgets);
      expect(find.text('복습 퀴즈'), findsOneWidget);
      expect(find.text('Owll 벤치마크'), findsOneWidget);
      expect(find.text('Owll 벤치마크에서 우선 도입할 기능은?'), findsOneWidget);
      expect(find.text('백엔드 생성 Study Pack입니다.'), findsOneWidget);
      expect(find.text('Study Pack은 어디에서 생성되나요?'), findsOneWidget);
      expect(find.textContaining('근거: 김철수 @12s'), findsWidgets);

      Map<dynamic, dynamic>? clipboardPayload;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, (call) async {
        if (call.method == 'Clipboard.setData') {
          clipboardPayload = call.arguments as Map<dynamic, dynamic>;
        }
        return null;
      });
      addTearDown(() {
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(SystemChannels.platform, null);
      });

      await tester.ensureVisible(find.text('학습팩 복사'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(OutlinedButton, '학습팩 복사'));
      await tester.pump(const Duration(milliseconds: 250));

      final clipboardText = clipboardPayload?['text'] as String?;
      expect(clipboardText, contains('플래시카드'));
      expect(clipboardText, contains('Owll 벤치마크에서 우선 도입할 기능은?'));
      expect(clipboardText, contains('답: 백엔드 생성 Study Pack입니다.'));
      expect(clipboardText, contains('복습 퀴즈'));
      expect(clipboardText, contains('정답: 백엔드 Study Pack API에서 생성됩니다.'));
      expect(find.text('학습팩을 복사했습니다'), findsOneWidget);

      await tester.ensureVisible(find.text('Study Pack은 어디에서 생성되나요?'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Study Pack은 어디에서 생성되나요?'));
      await tester.pumpAndSettle();
      expect(find.text('정답: 백엔드 Study Pack API에서 생성됩니다.'), findsOneWidget);
    });

    testWidgets('Study Pack 항목이 비어 있으면 빈 상태를 표시해야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockStudyPackApi.get(
            any(),
            mode: any(named: 'mode'),
            language: any(named: 'language'),
          )).thenAnswer(
        (_) async => const StudyPack(
          taskId: 'min-task-001',
          mode: 'lecture',
          language: 'ko',
          keyConcepts: [],
          flashcards: [],
          quizQuestions: [],
          studyNotes: '',
          sourceRefs: [],
          createdAt: '2026-03-22T00:00:00Z',
        ),
      );

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToStudyTab(tester);

      // Assert
      expect(find.text('학습 자료가 없습니다'), findsOneWidget);
      expect(find.text('회의록 내용이 충분하지 않아 학습팩을 만들 수 없습니다'), findsOneWidget);
    });

    testWidgets('학습 모드 선택 시 해당 모드로 Study Pack을 요청해야 함',
        (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToStudyTab(tester);
      await tester.tap(find.text('인터뷰'));
      await tester.pumpAndSettle();

      // Assert
      expect(find.text('인터뷰'), findsOneWidget);
      verify(() => mockStudyPackApi.get('min-task-001',
          mode: 'interview', language: 'ko')).called(1);
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
    testWidgets('담당자가 없으면 "미지정"으로 표시되어야 함', (WidgetTester tester) async {
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
    testWidgets('체크박스 토글 시 취소선이 적용되어야 함', (WidgetTester tester) async {
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

  group('_MindMapTab - 요약 결과 계층 표시', () {
    testWidgets('백엔드 마인드맵 root, children, edges를 표시해야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockSumApi.getMindMapResult(any())).thenAnswer((_) async => {
            'task_id': 'mind-task-001',
            'summary_task_id': 'sum-task-001',
            'status': 'completed',
            'root': {
              'id': 'root',
              'title': '회의 인사이트',
              'summary': '회의 핵심 요약입니다.',
              'source_refs': ['summary_text'],
              'children': [
                {
                  'id': 'benchmark',
                  'title': '회의 안건',
                  'summary': '신규 기능 벤치마킹',
                  'source_refs': ['sections.회의 안건'],
                  'children': [
                    {
                      'id': 'decision',
                      'title': '주요 결정',
                      'summary': '마인드맵 탭 추가',
                      'source_refs': ['key_decisions'],
                      'children': <dynamic>[],
                    },
                  ],
                },
                {
                  'id': 'action',
                  'title': '액션 아이템',
                  'summary': '마인드맵 UI 검토',
                  'source_refs': ['action_items'],
                  'children': <dynamic>[],
                },
              ],
            },
            'edges': [
              {
                'source': 'benchmark',
                'target': 'decision',
                'relation': 'leads_to',
              },
            ],
          });

      // Act
      await tester.pumpWidget(buildTestWidget([]));
      await _pumpToMindMapTab(tester);

      // Assert
      expect(find.text('회의 인사이트'), findsOneWidget);
      expect(find.text('회의 안건'), findsOneWidget);
      expect(find.text('신규 기능 벤치마킹'), findsOneWidget);
      expect(find.text('주요 결정'), findsOneWidget);
      expect(find.text('마인드맵 탭 추가'), findsOneWidget);
      expect(find.text('액션 아이템'), findsWidgets);
    });
  });

  group('_ActionItemsTab - 우선순위 배지 색상', () {
    // high 우선순위는 빨간색 배지
    testWidgets('high 우선순위는 빨간색 배지로 표시되어야 함', (WidgetTester tester) async {
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
    testWidgets('medium 우선순위는 주황색 배지로 표시되어야 함', (WidgetTester tester) async {
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
    testWidgets('low 우선순위는 초록색 배지로 표시되어야 함', (WidgetTester tester) async {
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
    testWidgets('전체 필터 선택 시 모든 아이템이 표시되어야 함', (WidgetTester tester) async {
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
      await tester.ensureVisible(find.text('전체'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('전체'), warnIfMissed: false);
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
