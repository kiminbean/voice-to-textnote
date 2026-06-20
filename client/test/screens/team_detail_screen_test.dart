// TeamDetailScreen 위젯 테스트 - auth 사용자 기반 권한 표시
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/auth_user.dart';
import 'package:voice_to_textnote/models/team.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/screens/team_detail_screen.dart';
import 'package:voice_to_textnote/services/team_api.dart';

class MockTeamApi extends Mock implements TeamApi {}

void main() {
  late MockTeamApi mockTeamApi;

  final detail = TeamDetail(
    id: 'team-1',
    name: '프로덕트 팀',
    description: '회의록 공유 팀',
    createdBy: 'user-admin',
    createdAt: DateTime(2026, 3, 22),
    memberCount: 2,
    members: [
      TeamMember(
        userId: 'user-admin',
        email: 'admin@example.com',
        displayName: '관리자',
        role: 'admin',
        joinedAt: DateTime(2026, 3, 22),
      ),
      TeamMember(
        userId: 'user-member',
        email: 'member@example.com',
        displayName: '멤버',
        role: 'member',
        joinedAt: DateTime(2026, 3, 23),
      ),
    ],
  );

  setUp(() {
    mockTeamApi = MockTeamApi();
    when(() => mockTeamApi.getTeamDetail('team-1'))
        .thenAnswer((_) async => detail);
    when(() => mockTeamApi.getTeamMeetings('team-1'))
        .thenAnswer((_) async => <Map<String, dynamic>>[]);
  });

  Widget buildTestWidget(AuthUser user) {
    return ProviderScope(
      overrides: [
        teamApiProvider.overrideWithValue(mockTeamApi),
        currentUserProvider.overrideWithValue(user),
      ],
      child: const MaterialApp(
        home: TeamDetailScreen(teamId: 'team-1'),
      ),
    );
  }

  testWidgets('현재 사용자가 admin이면 팀 편집과 초대 액션을 표시해야 함',
      (WidgetTester tester) async {
    await tester.pumpWidget(buildTestWidget(const AuthUser(
      id: 'user-admin',
      email: 'admin@example.com',
      displayName: '관리자',
      isActive: true,
    )));
    await tester.pumpAndSettle();

    expect(find.text('프로덕트 팀'), findsOneWidget);
    expect(find.byTooltip('팀 편집'), findsOneWidget);
    expect(find.text('멤버 초대'), findsOneWidget);
    expect(find.text('팀 삭제'), findsOneWidget);
    expect(find.text('(나)'), findsOneWidget);
    expect(find.byTooltip('제거'), findsOneWidget);
  });

  testWidgets('현재 사용자가 member이면 관리자 액션 대신 팀 나가기를 표시해야 함',
      (WidgetTester tester) async {
    await tester.pumpWidget(buildTestWidget(const AuthUser(
      id: 'user-member',
      email: 'member@example.com',
      displayName: '멤버',
      isActive: true,
    )));
    await tester.pumpAndSettle();

    expect(find.byTooltip('팀 편집'), findsNothing);
    expect(find.text('멤버 초대'), findsNothing);
    expect(find.text('팀 삭제'), findsNothing);
    expect(find.text('팀 나가기'), findsOneWidget);
    expect(find.text('(나)'), findsOneWidget);
    expect(find.byTooltip('제거'), findsNothing);
  });
}
