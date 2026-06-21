import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/widgets/meeting_card.dart';

void main() {
  group('MeetingCard privacy badge', () {
    testWidgets('공유 팀이 없으면 비공개 배지를 표시해야 함', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MeetingCard(
              meeting: Meeting(
                id: 'private-001',
                title: '개인 메모',
                createdAt: DateTime(2024, 1, 15),
                status: MeetingStatus.completed,
              ),
            ),
          ),
        ),
      );

      expect(find.text('비공개'), findsOneWidget);
      expect(find.byIcon(Icons.lock_outline_rounded), findsOneWidget);
    });

    testWidgets('공유 팀이 있으면 팀 공유 배지를 표시해야 함', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MeetingCard(
              meeting: Meeting(
                id: 'shared-001',
                title: '팀 회의',
                createdAt: DateTime(2024, 1, 15),
                status: MeetingStatus.completed,
                sharedTeamIds: const ['team-001'],
              ),
            ),
          ),
        ),
      );

      expect(find.text('팀 공유'), findsOneWidget);
      expect(find.byIcon(Icons.groups_2_outlined), findsOneWidget);
    });
  });
}
