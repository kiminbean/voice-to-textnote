import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/services/team_api.dart';
import 'package:voice_to_textnote/widgets/team_share_dialog.dart';

class MockTeamApi extends Mock implements TeamApi {}

Team _team({
  required String id,
  required String name,
  String? description,
}) =>
    Team(
      id: id,
      name: name,
      description: description,
      createdBy: 'user-001',
      createdAt: DateTime(2024, 1, 15),
      memberCount: 3,
    );

void main() {
  group('TeamShareDialog privacy policy', () {
    late MockTeamApi api;

    setUp(() {
      api = MockTeamApi();
      when(() => api.getTeams()).thenAnswer(
        (_) async => [
          _team(
            id: 'team-001',
            name: '리서치 팀',
            description: '사용자 인터뷰 공유',
          ),
          _team(id: 'team-002', name: '제품 팀'),
        ],
      );
      when(() => api.shareMeeting(any(), any())).thenAnswer(
        (_) async => MeetingShareResponse(
          taskId: 'meeting-001',
          teamId: 'team-001',
          sharedAt: DateTime(2024, 1, 15),
        ),
      );
      when(() => api.unshareMeeting(any(), any())).thenAnswer((_) async {});
    });

    Future<void> pumpDialog(
      WidgetTester tester, {
      Set<String> initiallySharedTeamIds = const {},
    }) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [teamApiProvider.overrideWithValue(api)],
          child: MaterialApp(
            home: Scaffold(
              body: TeamShareDialog(
                taskId: 'meeting-001',
                initiallySharedTeamIds: initiallySharedTeamIds,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('공유 전에는 비공개 기본 정책과 나만 볼 수 있음을 표시해야 함', (tester) async {
      await pumpDialog(tester);

      expect(find.text('기본은 비공개입니다. 선택한 팀만 이 노트에 접근할 수 있습니다.'), findsOneWidget);
      expect(find.text('나만 볼 수 있음'), findsOneWidget);
      expect(find.text('리서치 팀'), findsOneWidget);
      expect(find.text('사용자 인터뷰 공유'), findsOneWidget);
    });

    testWidgets('이미 공유된 팀이 있으면 공유 중 상태를 표시해야 함', (tester) async {
      await pumpDialog(tester, initiallySharedTeamIds: {'team-001'});

      expect(find.text('1개 팀에 공유 중'), findsOneWidget);
      expect(find.text('나만 볼 수 있음'), findsNothing);
    });

    testWidgets('팀을 선택하면 공유 중 상태 요약이 갱신되어야 함', (tester) async {
      await pumpDialog(tester);

      await tester.tap(find.text('리서치 팀'));
      await tester.pumpAndSettle();

      expect(find.text('1개 팀에 공유 중'), findsOneWidget);
      verify(() => api.shareMeeting('meeting-001', 'team-001')).called(1);
    });
  });
}
