// HomeScreen 위젯 테스트
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
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
    registerFallbackValue(const Duration(seconds: 30));
  });

  group('HomeScreen', () {
    late MockConnectivityService mockService;

    setUp(() {
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

      // AppBar 타이틀 확인
      expect(find.text('Voice to TextNote'), findsOneWidget);

      // 빈 상태 메시지 확인
      expect(find.text('녹음된 미팅이 없습니다'), findsOneWidget);

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

      // 미팅 카드가 표시되어야 함
      expect(find.text('테스트 미팅'), findsOneWidget);
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
