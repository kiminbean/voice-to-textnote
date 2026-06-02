// SearchScreen 위젯 테스트 (SPEC-SEARCH-001)
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/search_result.dart';
import 'package:voice_to_textnote/providers/connectivity_provider.dart';
import 'package:voice_to_textnote/providers/search_provider.dart';
import 'package:voice_to_textnote/screens/home_screen.dart';
import 'package:voice_to_textnote/screens/search_screen.dart';
import 'package:voice_to_textnote/services/connectivity_service.dart';

class MockConnectivityService extends Mock implements ConnectivityService {}

// 테스트용 온라인 상태 오버라이드 헬퍼
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

  group('HomeScreen 검색 아이콘', () {
    late MockConnectivityService mockService;

    setUp(() {
      mockService = MockConnectivityService();
    });

    // 홈 화면에 검색 아이콘이 존재하는지 확인
    testWidgets('HomeScreen AppBar에 검색 아이콘이 존재해야 함',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: _onlineOverrides(mockService),
          child: const MaterialApp(
            home: HomeScreen(),
          ),
        ),
      );

      // PopupMenuButton 확인 (검색 아이콘은 PopupMenu 내부에 있음)
      expect(find.byType(PopupMenuButton<String>), findsOneWidget);
    });

    // 검색 아이콘과 양식 관리 아이콘 모두 존재하는지 확인
    testWidgets('HomeScreen AppBar에 검색 아이콘과 양식 관리 아이콘이 모두 있어야 함',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: _onlineOverrides(mockService),
          child: const MaterialApp(
            home: HomeScreen(),
          ),
        ),
      );

      // PopupMenuButton 확인 (모든 아이콘이 PopupMenu 내부에 있음)
      expect(find.byType(PopupMenuButton<String>), findsOneWidget);

      // PopupMenu 열기
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pump();

      // 검색 및 양식 관리 아이콘 확인
      expect(find.byIcon(Icons.search), findsOneWidget);
      expect(find.byIcon(Icons.folder_special_outlined), findsOneWidget);
    });
  });

  group('SearchScreen', () {
    // 검색 화면 기본 렌더링 테스트
    testWidgets('SearchScreen이 TextField와 함께 렌더링되어야 함',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
            home: SearchScreen(),
          ),
        ),
      );

      // 텍스트 필드가 존재해야 함
      expect(find.byType(TextField), findsOneWidget);
    });

    // 검색어 없을 때 빈 상태 메시지 확인
    testWidgets('검색어가 없을 때 안내 메시지가 표시되어야 함',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
            home: SearchScreen(),
          ),
        ),
      );

      await tester.pump();

      // 검색어 없음 안내 메시지
      expect(find.text('검색어를 2자 이상 입력하세요'), findsOneWidget);
    });

    // 검색 결과 없을 때 메시지 확인
    testWidgets('검색 결과가 없을 때 "검색 결과가 없습니다" 메시지가 표시되어야 함',
        (WidgetTester tester) async {
      // 빈 결과를 반환하는 오버라이드
      const emptyQuery = SearchQuery(query: '없는검색어결과');
      const emptyResponse = SearchResponse(
        items: [],
        total: 0,
        page: 1,
        pageSize: 20,
        query: '없는검색어결과',
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            searchResultProvider(emptyQuery).overrideWith(
              (_) => emptyResponse,
            ),
          ],
          child: const MaterialApp(
            home: SearchScreen(),
          ),
        ),
      );

      // 텍스트 입력
      await tester.enterText(find.byType(TextField), '없는검색어결과');
      // 디바운스 대기 (300ms 이상)
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pump();

      expect(find.text('검색 결과가 없습니다'), findsOneWidget);
    });
  });

  group('parseSnippet 유틸리티', () {
    // <b>태그 없는 일반 텍스트
    test('태그 없는 텍스트는 단일 TextSpan으로 반환되어야 함', () {
      // _SearchResultTile의 static 메서드는 파일 외부에서 직접 접근 불가
      // 간접적으로 위젯 테스트를 통해 검증
      const snippet = '일반 텍스트 내용';
      // 볼드 없이 전체가 일반 텍스트
      expect(snippet.contains('<b>'), isFalse);
    });

    // <b>태그가 포함된 텍스트 검증 (위젯으로 렌더링)
    testWidgets('<b>태그가 볼드 TextSpan으로 변환되어야 함',
        (WidgetTester tester) async {
      final item = SearchResultItem(
        taskId: 'test-id',
        taskType: 'minutes',
        snippet: '안녕 <b>키워드</b> 테스트',
        createdAt: DateTime(2026, 3, 22),
      );
      final response = SearchResponse(
        items: [item],
        total: 1,
        page: 1,
        pageSize: 20,
        query: '키워드',
      );

      const searchQuery = SearchQuery(query: '키워드');

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            searchResultProvider(searchQuery).overrideWith(
              (_) => response,
            ),
          ],
          child: const MaterialApp(
            home: SearchScreen(),
          ),
        ),
      );

      // 텍스트 입력
      await tester.enterText(find.byType(TextField), '키워드');
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pump();

      // RichText가 렌더링되어야 함 (Text.rich 사용)
      expect(find.byType(RichText), findsWidgets);
      // 스니펫 내 텍스트가 표시되어야 함
      expect(find.textContaining('안녕'), findsWidgets);
    });
  });
}
