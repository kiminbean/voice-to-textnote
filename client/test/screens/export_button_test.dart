// ResultScreen - PDF 내보내기 버튼 위젯 테스트 - SPEC-EXPORT-001
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

// 테스트용 Meeting 목록 Notifier (AsyncNotifier이므로 Future<List<Meeting>> 반환)
class _MockMeetingListNotifier extends MeetingListNotifier {
  final List<Meeting> _meetings;
  _MockMeetingListNotifier(this._meetings);

  @override
  Future<List<Meeting>> build() async => _meetings;
}

void main() {
  late MockMinutesApi mockMinApi;
  late MockSummaryApi mockSumApi;

  // minutesTaskId가 있는 완료된 미팅 (PDF 내보내기 가능)
  final completedMeeting = Meeting(
    id: 'meeting-export-001',
    title: '내보내기 테스트 회의',
    createdAt: DateTime(2026, 3, 22),
    status: MeetingStatus.completed,
    minutesTaskId: 'min-task-export-001',
    summaryTaskId: 'sum-task-export-001',
  );

  // minutesTaskId가 없는 미팅 (PDF 내보내기 불가)
  final incompleteMeeting = Meeting(
    id: 'meeting-incomplete-001',
    title: '미완료 회의',
    createdAt: DateTime(2026, 3, 22),
    status: MeetingStatus.processing,
    minutesTaskId: null,
    summaryTaskId: null,
  );

  setUp(() {
    mockMinApi = MockMinutesApi();
    mockSumApi = MockSummaryApi();

    // 기본 API 응답 설정
    when(() => mockMinApi.getResult(any())).thenAnswer(
      (_) async => {'markdown': '# 회의록\n내용'},
    );
    when(() => mockSumApi.getResult(any())).thenAnswer(
      (_) async => {
        'summary_text': '요약 내용',
        'action_items': <dynamic>[],
        'key_decisions': <dynamic>[],
        'next_steps': <dynamic>[],
      },
    );
    when(() => mockSumApi.createMindMap(any())).thenAnswer(
      (_) async => {'task_id': 'mind-task-export-001', 'status': 'pending'},
    );
    when(() => mockSumApi.getMindMapStatus(any())).thenAnswer(
      (_) async => {'status': 'completed'},
    );
    when(() => mockSumApi.getMindMapResult(any())).thenAnswer(
      (_) async => {
        'task_id': 'mind-task-export-001',
        'summary_task_id': 'sum-task-export-001',
        'status': 'completed',
        'root': {
          'id': 'root',
          'title': '회의 인사이트',
          'summary': '요약 내용',
          'children': <dynamic>[],
          'source_refs': <dynamic>[],
        },
        'edges': <dynamic>[],
      },
    );
  });

  // 위젯 테스트 헬퍼
  Widget buildTestWidget(Meeting meeting) {
    return ProviderScope(
      overrides: [
        minutesApiProvider.overrideWithValue(mockMinApi),
        summaryApiProvider.overrideWithValue(mockSumApi),
        meetingListProvider.overrideWith(
          () => _MockMeetingListNotifier([meeting]),
        ),
      ],
      child: MaterialApp(
        home: ResultScreen(meetingId: meeting.id),
      ),
    );
  }

  group('ResultScreen AppBar - PDF 내보내기 버튼', () {
    // AppBar에 PDF 내보내기 아이콘 버튼이 존재하는지 테스트
    testWidgets('AppBar에 PDF 내보내기 아이콘 버튼이 표시되어야 함',
        (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(buildTestWidget(completedMeeting));
      await tester.pumpAndSettle();

      // Assert: picture_as_pdf_outlined 아이콘 존재 확인
      expect(
        find.byIcon(Icons.picture_as_pdf_outlined),
        findsOneWidget,
      );
    });

    // 버튼이 AppBar actions 영역에 위치하는지 테스트
    testWidgets('PDF 내보내기 버튼이 AppBar의 actions 영역에 있어야 함',
        (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(buildTestWidget(completedMeeting));
      await tester.pumpAndSettle();

      // Assert: IconButton이 AppBar 내에 존재
      final appBar = find.byType(AppBar);
      expect(appBar, findsOneWidget);

      // AppBar 내에 PDF 아이콘 버튼이 있어야 함
      expect(
        find.descendant(
          of: appBar,
          matching: find.byIcon(Icons.picture_as_pdf_outlined),
        ),
        findsOneWidget,
      );
    });

    // minutesTaskId가 없을 때도 버튼이 표시되는지 테스트
    testWidgets('minutesTaskId가 없어도 PDF 내보내기 버튼이 표시되어야 함',
        (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(buildTestWidget(incompleteMeeting));
      await tester.pumpAndSettle();

      // Assert: 버튼은 표시되지만 탭 시 SnackBar 표시 (별도 테스트)
      expect(
        find.byIcon(Icons.picture_as_pdf_outlined),
        findsOneWidget,
      );
    });

    // AppBar 제목이 올바르게 표시되는지 테스트
    testWidgets('AppBar 제목이 "회의 결과"로 표시되어야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(buildTestWidget(completedMeeting));
      await tester.pumpAndSettle();

      // Assert
      expect(find.text('회의 결과'), findsOneWidget);
    });
  });

  group('ResultScreen - TabBar 구조', () {
    // 결과 탭이 올바르게 표시되는지 테스트
    testWidgets('회의록/AI 요약/마인드맵/액션 아이템 탭이 표시되어야 함',
        (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(buildTestWidget(completedMeeting));
      await tester.pumpAndSettle();

      // Assert: 탭 레이블 확인 (TabBar 내에 Tab 위젯 존재 여부로 확인)
      // "회의록" 텍스트는 TabBar와 SpeakerSegment 헤더에 중복될 수 있어 findsWidgets 사용
      expect(find.text('회의록'), findsWidgets);
      expect(find.text('AI 요약'), findsOneWidget);
      expect(find.text('마인드맵'), findsOneWidget);
      expect(find.text('액션 아이템'), findsOneWidget);
    });

    // 탭 전환이 동작하는지 테스트
    testWidgets('AI 요약 탭으로 전환이 가능해야 함', (WidgetTester tester) async {
      // Act
      await tester.pumpWidget(buildTestWidget(completedMeeting));
      await tester.pumpAndSettle();
      await tester.tap(find.text('AI 요약'));
      await tester.pumpAndSettle();

      // Assert: 탭 전환 후 오류 없이 렌더링
      expect(find.byType(TabBarView), findsOneWidget);
    });
  });
}
