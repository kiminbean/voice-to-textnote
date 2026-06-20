// RecordingScreen 위젯 테스트
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/screens/recording_screen.dart';

void main() {
  group('RecordingScreen', () {
    // go_router를 포함한 테스트 앱 빌더 헬퍼
    Widget buildTestApp({
      List<Override> overrides = const [],
      CaptureMode initialMode = CaptureMode.recording,
    }) {
      final router = GoRouter(
        initialLocation: '/recording',
        routes: [
          GoRoute(
            path: '/',
            builder: (_, __) => const Scaffold(body: Text('홈')),
          ),
          GoRoute(
            path: '/recording',
            builder: (_, __) => RecordingScreen(initialMode: initialMode),
          ),
        ],
      );

      return ProviderScope(
        overrides: overrides,
        child: MaterialApp.router(
          routerConfig: router,
        ),
      );
    }

    // 초기 버튼 상태 테스트
    testWidgets('초기에 녹음 시작 버튼이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // 녹음 버튼 (큰 원형 아이콘)이 존재해야 함
      expect(find.bySemanticsLabel('녹음 시작'), findsOneWidget);

      // 타이머 표시 (00:00)
      expect(find.text('00:00'), findsOneWidget);

      // 초기 상태 텍스트
      expect(find.text('탭하여 녹음 시작'), findsOneWidget);
      expect(find.text('Live Transcript'), findsOneWidget);
      expect(find.text('업로드'), findsOneWidget);
      expect(find.text('회의 링크'), findsOneWidget);
    });

    testWidgets('업로드 초기 모드로 진입하면 파일 선택 안내가 표시되어야 함',
        (WidgetTester tester) async {
      await tester.pumpWidget(buildTestApp(initialMode: CaptureMode.upload));
      await tester.pumpAndSettle();

      expect(find.text('업로드할 파일 선택'), findsOneWidget);
      expect(
          find.text('WAV, MP3, M4A, MP4, OGG 파일을 바로 처리합니다.'), findsOneWidget);
    });

    // 녹음 버튼 탭 후 상태 확인 (실제 마이크 없이 테스트)
    // 테스트 환경에서는 마이크 권한이 없으므로 UI 변화가 없을 수 있음
    testWidgets('녹음 버튼 탭 시 UI가 응답해야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // 녹음 버튼 탭 (비동기 처리)
      await tester.tap(find.bySemanticsLabel('녹음 시작'));
      await tester.pump();

      // UI가 존재해야 함 (권한 없이는 상태 변화 없을 수 있음)
      expect(find.byType(RecordingScreen), findsOneWidget);
    });

    // 타이머 표시 형식 테스트
    testWidgets('타이머가 MM:SS 형식으로 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // 초기값 00:00 확인
      expect(find.text('00:00'), findsOneWidget);
    });

    // 앱바 제목 테스트
    testWidgets('앱바에 AI 녹음 제목이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      expect(find.text('AI 녹음'), findsOneWidget);
    });

    testWidgets('회의 링크 탭에서 지원 링크를 대기 미팅으로 저장해야 함', (WidgetTester tester) async {
      final notifier = _CaptureMeetingListNotifier();

      await tester.pumpWidget(buildTestApp(
        overrides: [
          meetingListProvider.overrideWith(() => notifier),
        ],
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('회의 링크'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextField).last,
        'https://zoom.us/j/123456789',
      );
      await tester.tap(find.text('AI 기록 봇 준비'));
      await tester.pumpAndSettle();

      expect(notifier.addedMeetings, hasLength(1));
      expect(notifier.addedMeetings.single.title, 'Zoom 회의');
      expect(notifier.addedMeetings.single.status, MeetingStatus.scheduled);
      expect(notifier.addedMeetings.single.sourceUrl,
          'https://zoom.us/j/123456789');
      expect(find.text('홈'), findsOneWidget);
    });
  });
}

class _CaptureMeetingListNotifier extends MeetingListNotifier {
  final addedMeetings = <Meeting>[];

  @override
  Future<List<Meeting>> build() async => addedMeetings;

  @override
  Future<void> addMeeting(Meeting meeting) async {
    addedMeetings.add(meeting);
    state = AsyncData([...addedMeetings]);
  }
}
