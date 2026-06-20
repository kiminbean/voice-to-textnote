// TeamListScreen 위젯 테스트 - 팀 생성 다이얼로그 흐름
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/screens/team_list_screen.dart';
import 'package:voice_to_textnote/services/team_api.dart';

class MockTeamApi extends Mock implements TeamApi {}

void main() {
  late MockTeamApi mockTeamApi;

  final createdTeam = Team(
    id: 'team-1',
    name: '프로덕트 팀',
    description: '회의록 공유 팀',
    createdBy: 'user-1',
    createdAt: DateTime(2026, 6, 20),
    memberCount: 1,
  );

  setUp(() {
    mockTeamApi = MockTeamApi();
    when(() => mockTeamApi.getTeams()).thenAnswer((_) async => <Team>[]);
    when(
      () => mockTeamApi.createTeam(
        name: any(named: 'name'),
        description: any(named: 'description'),
      ),
    ).thenAnswer((_) async => createdTeam);
  });

  Widget buildTestWidget() {
    return ProviderScope(
      overrides: [
        teamApiProvider.overrideWithValue(mockTeamApi),
      ],
      child: const MaterialApp(
        home: TeamListScreen(),
      ),
    );
  }

  testWidgets('팀 생성 다이얼로그 입력값을 API로 전달해야 함', (tester) async {
    await tester.pumpWidget(buildTestWidget());
    await tester.pumpAndSettle();

    await tester.tap(find.text('팀 생성'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField).first, '  프로덕트 팀  ');
    await tester.enterText(find.byType(TextFormField).last, '  회의록 공유 팀  ');
    await tester.tap(find.text('만들기'));
    await tester.pumpAndSettle();

    verify(
      () => mockTeamApi.createTeam(
        name: '프로덕트 팀',
        description: '회의록 공유 팀',
      ),
    ).called(1);
    expect(find.text('팀 "프로덕트 팀"이 생성되었습니다'), findsOneWidget);
  });
}
