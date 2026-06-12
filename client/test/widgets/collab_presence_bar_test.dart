// M4 위젯 테스트: CollabPresenceBar, CollabEditingIndicator
// SPEC-COLLAB-001: AC-040 ~ AC-045
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/collab_socket_service.dart';
import 'package:voice_to_textnote/widgets/collab_presence_bar.dart';
import 'package:voice_to_textnote/widgets/collab_editing_indicator.dart';

void main() {
  // AC-042: Presence 표시
  group('CollabPresenceBar', () {
    testWidgets('AC-042: 활성 사용자가 없으면 렌더링하지 않는다', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: CollabPresenceBar(activeUsers: [])),
        ),
      );
      expect(find.byType(CollabPresenceBar), findsOneWidget);
      expect(find.text('명 편집 중'), findsNothing);
    });

    testWidgets('AC-042: 3명 접속 시 아바타 3개 + "3명 편집 중" 텍스트',
        (tester) async {
      final users = [
        const CollabUser(userId: 'a', displayName: 'Alice', color: '#FF5733'),
        const CollabUser(userId: 'b', displayName: 'Bob', color: '#33FF57'),
        const CollabUser(userId: 'c', displayName: 'Charlie', color: '#3357FF'),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 400,
              child: CollabPresenceBar(activeUsers: users),
            ),
          ),
        ),
      );

      expect(find.text('3명 편집 중'), findsOneWidget);
      // 아바타 이니셜 확인
      expect(find.text('A'), findsOneWidget);
      expect(find.text('B'), findsOneWidget);
      expect(find.text('C'), findsOneWidget);
    });

    testWidgets('AC-042: 5명 초과 시 +N 오버플로우 표시', (tester) async {
      final users = List.generate(
        7,
        (i) => CollabUser(
          userId: 'u$i',
          displayName: 'User$i',
          color: '#FF$i',
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 400,
              child: CollabPresenceBar(activeUsers: users),
            ),
          ),
        ),
      );

      expect(find.text('7명 편집 중'), findsOneWidget);
      expect(find.text('+2'), findsOneWidget);
    });

    testWidgets('AC-042: 빈 color면 기본 파란색 사용', (tester) async {
      final users = [
        const CollabUser(userId: 'a', displayName: 'Alice', color: ''),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 400,
              child: CollabPresenceBar(activeUsers: users),
            ),
          ),
        ),
      );

      // 렌더링 성공 확인 (에러 없이)
      expect(find.text('1명 편집 중'), findsOneWidget);
      expect(find.text('A'), findsOneWidget);
    });
  });

  // AC-041, AC-043: 편집 중 표시
  group('CollabEditingIndicator', () {
    testWidgets('AC-043: 편집 중이 아니면 렌더링하지 않는다', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CollabEditingIndicator(),
          ),
        ),
      );

      // SizedBox.shrink 반환 → 텍스트 없음
      expect(find.text('편집 중'), findsNothing);
    });

    testWidgets('AC-043: 다른 사용자 편집 중이면 이름과 색상 표시', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CollabEditingIndicator(
              editingUserName: 'Alice',
              editingUserColor: '#FF5733',
              isBeingEditedByOther: true,
            ),
          ),
        ),
      );

      expect(find.textContaining('Alice 편집 중'), findsOneWidget);
      // 색상 점 표시 확인
      expect(find.byType(Container), findsWidgets);
    });

    testWidgets('AC-043: 이름 없으면 렌더링하지 않는다', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CollabEditingIndicator(
              editingUserName: null,
              isBeingEditedByOther: true,
            ),
          ),
        ),
      );

      expect(find.textContaining('편집 중'), findsNothing);
    });

    testWidgets('AC-041: 빈 color면 기본 주황색 사용', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: CollabEditingIndicator(
              editingUserName: 'Bob',
              editingUserColor: '',
              isBeingEditedByOther: true,
            ),
          ),
        ),
      );

      expect(find.textContaining('Bob 편집 중'), findsOneWidget);
    });
  });
}
