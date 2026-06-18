// ResultScreen PDF 내보내기 동작 테스트 - SPEC-EXPORT-001 Phase 3
// 로딩 상태 및 에러 SnackBar 동작 검증
import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/screens/result_screen.dart';
import 'package:voice_to_textnote/services/export_api.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';

class MockMinutesApi extends Mock implements MinutesApi {}

class MockSummaryApi extends Mock implements SummaryApi {}

class MockExportApi extends Mock implements ExportApi {}

// 테스트용 MeetingListNotifier
class _FakeMeetingListNotifier extends MeetingListNotifier {
  final List<Meeting> _meetings;
  _FakeMeetingListNotifier(this._meetings);

  @override
  Future<List<Meeting>> build() async => _meetings;
}

void main() {
  late MockMinutesApi mockMinApi;
  late MockSummaryApi mockSumApi;
  late MockExportApi mockExportApi;

  // minutesTaskId가 있는 완료된 미팅
  final completedMeeting = Meeting(
    id: 'meeting-loading-001',
    title: '내보내기 로딩 테스트 회의',
    createdAt: DateTime(2026, 3, 22),
    status: MeetingStatus.completed,
    minutesTaskId: 'min-task-loading-001',
    summaryTaskId: 'sum-task-loading-001',
  );

  // minutesTaskId가 없는 미팅
  final incompleteMeeting = Meeting(
    id: 'meeting-no-task-001',
    title: '미완료 회의',
    createdAt: DateTime(2026, 3, 22),
    status: MeetingStatus.processing,
    minutesTaskId: null,
    summaryTaskId: null,
  );

  setUp(() {
    mockMinApi = MockMinutesApi();
    mockSumApi = MockSummaryApi();
    mockExportApi = MockExportApi();

    // API 기본 응답 설정
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
  });

  // 위젯 빌더 - ExportApi 오버라이드 포함
  Widget buildTestWidget(Meeting meeting) {
    return ProviderScope(
      overrides: [
        minutesApiProvider.overrideWithValue(mockMinApi),
        summaryApiProvider.overrideWithValue(mockSumApi),
        exportApiProvider.overrideWithValue(mockExportApi),
        meetingListProvider.overrideWith(
          () => _FakeMeetingListNotifier([meeting]),
        ),
      ],
      child: MaterialApp(
        home: ResultScreen(meetingId: meeting.id),
      ),
    );
  }

  group('ResultScreen - PDF 내보내기 로딩 상태', () {
    // 다운로드 진행 중에 CircularProgressIndicator가 표시되어야 함
    testWidgets('PDF 다운로드 중 CircularProgressIndicator가 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange: downloadPdf가 완료되지 않는 Completer로 지연
      final completer = Completer<File>();
      when(() => mockExportApi.downloadPdf(
            any(),
            summaryTaskId: any(named: 'summaryTaskId'),
          )).thenAnswer((_) => completer.future);

      // Act: 위젯 렌더링 후 팝업 열고 PDF 선택
      await tester.pumpWidget(buildTestWidget(completedMeeting));
      await tester.pumpAndSettle();

      // PopupMenuButton 트리거 탭 → 팝업 열기
      await tester.tap(find.byIcon(Icons.ios_share_rounded));
      await tester.pumpAndSettle();

      // 팝업에서 PDF 선택
      await tester.tap(find.text('PDF'));
      await tester.pump(); // setState 후 1 프레임 처리

      // Assert: CircularProgressIndicator가 표시되어야 함
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // 정리: Completer 완료
      completer.completeError(Exception('테스트 종료'));
      await tester.pumpAndSettle();
    });

    // 로딩 중에는 내보내기 버튼이 로딩 인디케이터로 교체되어야 함
    testWidgets('PDF 다운로드 중 ios_share 아이콘이 숨겨져야 함',
        (WidgetTester tester) async {
      // Arrange: 완료되지 않는 Future
      final completer = Completer<File>();
      when(() => mockExportApi.downloadPdf(
            any(),
            summaryTaskId: any(named: 'summaryTaskId'),
          )).thenAnswer((_) => completer.future);

      // Act
      await tester.pumpWidget(buildTestWidget(completedMeeting));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.ios_share_rounded));
      await tester.pumpAndSettle();

      await tester.tap(find.text('PDF'));
      await tester.pump();

      // Assert: 로딩 중에는 ios_share 아이콘이 없어야 함
      expect(find.byIcon(Icons.ios_share_rounded), findsNothing);

      // 정리
      completer.completeError(Exception('테스트 종료'));
      await tester.pumpAndSettle();
    });
  });

  group('ResultScreen - PDF 내보내기 에러 처리', () {
    // 내보내기 실패 시 SnackBar에 에러 메시지가 표시되어야 함
    testWidgets('ExportApi 실패 시 에러 SnackBar가 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange: downloadPdf가 DioException 발생
      when(() => mockExportApi.downloadPdf(
            any(),
            summaryTaskId: any(named: 'summaryTaskId'),
          )).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/export/pdf/min-task-loading-001'),
          type: DioExceptionType.connectionError,
          message: '연결 오류',
        ),
      );

      // Act
      await tester.pumpWidget(buildTestWidget(completedMeeting));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.ios_share_rounded));
      await tester.pumpAndSettle();

      await tester.tap(find.text('PDF'));
      await tester.pumpAndSettle();

      // Assert: SnackBar가 표시되어야 함
      expect(find.byType(SnackBar), findsOneWidget);
    });

    // minutesTaskId 없을 때 PDF 선택 시 SnackBar 표시 확인
    testWidgets('minutesTaskId 없을 때 PDF 선택하면 SnackBar가 표시되어야 함',
        (WidgetTester tester) async {
      // Act: minutesTaskId 없는 미팅으로 렌더링
      await tester.pumpWidget(buildTestWidget(incompleteMeeting));
      await tester.pumpAndSettle();

      // 팝업 열기
      await tester.tap(find.byIcon(Icons.ios_share_rounded));
      await tester.pumpAndSettle();

      // PDF 선택
      await tester.tap(find.text('PDF'));
      await tester.pumpAndSettle();

      // Assert: SnackBar가 표시되어야 함 (ExportApi 호출 없이)
      expect(find.byType(SnackBar), findsOneWidget);

      // ExportApi는 호출되지 않아야 함
      verifyNever(() => mockExportApi.downloadPdf(
            any(),
            summaryTaskId: any(named: 'summaryTaskId'),
          ));
    });

    // 에러 후 버튼이 다시 활성화되어야 함
    testWidgets('다운로드 실패 후 내보내기 버튼이 다시 표시되어야 함',
        (WidgetTester tester) async {
      // Arrange
      when(() => mockExportApi.downloadPdf(
            any(),
            summaryTaskId: any(named: 'summaryTaskId'),
          )).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/export/pdf/min-task-loading-001'),
          type: DioExceptionType.connectionError,
        ),
      );

      // Act
      await tester.pumpWidget(buildTestWidget(completedMeeting));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.ios_share_rounded));
      await tester.pumpAndSettle();

      await tester.tap(find.text('PDF'));
      await tester.pumpAndSettle();

      // Assert: 에러 후 ios_share 버튼이 다시 표시되어야 함
      expect(find.byIcon(Icons.ios_share_rounded), findsOneWidget);
    });
  });
}
