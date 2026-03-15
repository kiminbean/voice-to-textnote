// HomeScreen 위젯 테스트
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/screens/home_screen.dart';

void main() {
  group('HomeScreen', () {
    // 빈 상태 표시 테스트
    testWidgets('미팅이 없을 때 빈 상태 메시지가 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
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
    testWidgets('미팅이 있을 때 MeetingCard가 표시되어야 함', (WidgetTester tester) async {
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

// 테스트용 Mock Notifier
class _MockMeetingListNotifier extends MeetingListNotifier {
  final List<Meeting> _initialMeetings;

  _MockMeetingListNotifier(this._initialMeetings);

  @override
  List<Meeting> build() => _initialMeetings;
}
