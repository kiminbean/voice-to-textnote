// HomeScreen 위젯 테스트
// SPEC-HISTSYNC-001: RefreshIndicator, 삭제, 오류 처리 포함
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/connectivity_provider.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/screens/home_screen.dart';
import 'package:voice_to_textnote/services/connectivity_service.dart';

class MockConnectivityService extends Mock implements ConnectivityService {}

// 테스트용 온라인 상태 오버라이드
List<Override> _onlineOverrides(MockConnectivityService mockService) {
  final streamController = StreamController<bool>.broadcast();
  when(() => mockService.isOnline).thenReturn(true);
  when(() => mockService.onStatusChange)
      .thenAnswer((_) => streamController.stream);
  when(() => mockService.startMonitoring(
        interval: any(named: 'interval'),
      )).thenReturn(null);
  when(() => mockService.dispose()).thenReturn(null);

  return [
    connectivityServiceProvider.overrideWithValue(mockService),
  ];
}

void main() {
  setUpAll(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    registerFallbackValue(const Duration(seconds: 30));
  });

  group('HomeScreen', () {
    late MockConnectivityService mockService;

    setUp(() {
      // SharedPreferences mock 초기화 (meetingListProvider 기본값 사용 시 필요)
      SharedPreferences.setMockInitialValues({});
      mockService = MockConnectivityService();
    });

    // 빈 상태 표시 테스트
    testWidgets('미팅이 없을 때 빈 상태 메시지가 표시되어야 함',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: _onlineOverrides(mockService),
          child: const MaterialApp(
            home: HomeScreen(),
          ),
        ),
      );

      // AsyncNotifier 초기화 대기
      await tester.pumpAndSettle();

      // 헤더 타이틀 확인 (SliverAppBar.large는 확장/축소 상태 각각 렌더링)
      expect(find.text('회의 기록'), findsWidgets);

      // 빈 상태 메시지 확인
      expect(find.text('아직 녹음된 미팅이 없어요'), findsOneWidget);

      // FAB 버튼 확인
      expect(find.byType(FloatingActionButton), findsOneWidget);
    });

    // 미팅 목록 표시 테스트
    testWidgets('미팅이 있을 때 MeetingCard가 표시되어야 함',
        (WidgetTester tester) async {
      final testMeeting = Meeting(
        id: 'test-001',
        title: '테스트 미팅',
        createdAt: DateTime(2024, 1, 15),
        status: MeetingStatus.completed,
        duration: const Duration(minutes: 30),
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ..._onlineOverrides(mockService),
            meetingListProvider.overrideWith(
              () => _MockMeetingListNotifier([testMeeting]),
            ),
          ],
          child: const MaterialApp(
            home: HomeScreen(),
          ),
        ),
      );

      // AsyncNotifier 초기화 대기
      await tester.pumpAndSettle();

      // 미팅 카드가 표시되어야 함
      expect(find.text('테스트 미팅'), findsOneWidget);
    });

    // REQ-HSYNC-003: RefreshIndicator가 있어야 함
    testWidgets('홈 화면에 RefreshIndicator가 있어야 함',
        (WidgetTester tester) async {
      final testMeeting = Meeting(
        id: 'test-001',
        title: '테스트 미팅',
        createdAt: DateTime(2024, 1, 15),
        status: MeetingStatus.completed,
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ..._onlineOverrides(mockService),
            meetingListProvider.overrideWith(
              () => _MockMeetingListNotifier([testMeeting]),
            ),
          ],
          child: const MaterialApp(
            home: HomeScreen(),
          ),
        ),
      );

      // AsyncNotifier 초기화 대기
      await tester.pumpAndSettle();

      // RefreshIndicator가 있어야 함
      expect(find.byType(RefreshIndicator), findsOneWidget);
    });

    // REQ-HSYNC-005: 미팅 카드 롱프레스 시 삭제 다이얼로그 표시
    testWidgets('미팅 카드를 길게 누르면 삭제 확인 다이얼로그가 표시되어야 함',
        (WidgetTester tester) async {
      final testMeeting = Meeting(
        id: 'test-001',
        title: '삭제할 미팅',
        createdAt: DateTime(2024, 1, 15),
        status: MeetingStatus.completed,
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ..._onlineOverrides(mockService),
            meetingListProvider.overrideWith(
              () => _MockMeetingListNotifier([testMeeting]),
            ),
          ],
          child: const MaterialApp(
            home: HomeScreen(),
          ),
        ),
      );

      await tester.pump();

      // 미팅 카드를 길게 누름
      await tester.longPress(find.text('삭제할 미팅'));
      await tester.pumpAndSettle();

      // 삭제 확인 다이얼로그가 표시되어야 함
      expect(find.text('미팅 삭제'), findsOneWidget);
      expect(find.text('삭제'), findsOneWidget);
      expect(find.text('취소'), findsOneWidget);
    });
  });
}

// 테스트용 Mock Notifier (AsyncNotifier이므로 Future<List<Meeting>> 반환)
class _MockMeetingListNotifier extends MeetingListNotifier {
  final List<Meeting> _initialMeetings;

  _MockMeetingListNotifier(this._initialMeetings);

  @override
  Future<List<Meeting>> build() async => _initialMeetings;
}
