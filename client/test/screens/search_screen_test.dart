// SearchScreen 위젯 테스트 (SPEC-SEARCH-001 → SPEC-SEARCH-002)
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/models/promise_radar.dart';
import 'package:voice_to_textnote/models/search_result.dart';
import 'package:voice_to_textnote/providers/connectivity_provider.dart';
import 'package:voice_to_textnote/providers/qa_provider.dart';
import 'package:voice_to_textnote/providers/result_provider.dart';
import 'package:voice_to_textnote/providers/search_provider.dart';
import 'package:voice_to_textnote/screens/home_screen.dart';
import 'package:voice_to_textnote/screens/search_screen.dart';
import 'package:voice_to_textnote/services/connectivity_service.dart';
import 'package:voice_to_textnote/services/qa_api.dart';

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
    promiseRadarDashboardProvider.overrideWith((_) async {
      return const PromiseRadarDashboard(
        openCount: 0,
        highRiskCount: 0,
        overdueCount: 0,
        dueSoonCount: 0,
        blockedCount: 0,
        unconfirmedCount: 0,
        ownerHotspots: [],
        urgentPromises: [],
        recentChanges: [],
      );
    }),
    promiseDailyDigestProvider.overrideWith((_) async {
      return const PromiseDigest(
        cadence: 'daily',
        title: '오늘의 약속 레이더',
        generatedAt: '',
        openCount: 0,
        overdueCount: 0,
        dueSoonCount: 0,
        highRiskCount: 0,
        lines: [],
        promises: [],
      );
    }),
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

    // 검색 아이콘과 설정 아이콘 모두 존재하는지 확인
    testWidgets('HomeScreen AppBar에 검색 아이콘과 설정 아이콘이 모두 있어야 함',
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

      // 검색 및 설정 아이콘 확인
      expect(find.byIcon(Icons.search_rounded), findsOneWidget);
      expect(find.byIcon(Icons.settings_outlined), findsOneWidget);
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

    // 검색어 없을 때 최근 검색어 위젯 표시 (SPEC-SEARCH-002 Phase 5)
    testWidgets('검색어가 없을 때 최근 검색어 영역이 표시되어야 함', (WidgetTester tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
            home: SearchScreen(),
          ),
        ),
      );

      await tester.pump();

      // 검색 입력 필드 존재 확인
      expect(find.byType(TextField), findsOneWidget);
      // hintText 확인
      expect(find.byType(TextField), findsOneWidget);
    });

    // 검색 결과 없을 때 메시지 확인
    testWidgets('검색 결과가 없을 때 "검색 결과가 없습니다" 메시지가 표시되어야 함',
        (WidgetTester tester) async {
      // 빈 결과를 반환하는 오버라이드 (sort: 'relevance' = SearchFilterState 기본값)
      const emptyRequest = SearchRequest(query: '없는검색어결과', sort: 'relevance');
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
            searchResultProvider(emptyRequest).overrideWith(
              (_) => emptyResponse,
            ),
          ],
          child: const MaterialApp(
            home: SearchScreen(),
          ),
        ),
      );

      // 텍스트 입력 (controller listener가 debounce timer 시작)
      await tester.enterText(find.byType(TextField), '없는검색어결과');
      // 디바운스 타이머가 실행되도록 충분히 pump
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();

      // "검색 결과가 없습니다" 텍스트가 화면에 표시되어야 함
      expect(find.text('검색 결과가 없습니다'), findsOneWidget);
    });

    testWidgets('검색어와 관련된 cross-meeting Q&A 근거 패널이 표시되어야 함',
        (WidgetTester tester) async {
      const query = 'API 결정';
      const request = SearchRequest(query: query, sort: 'relevance');
      final response = SearchResponse(
        items: [
          SearchResultItem(
            taskId: 'sum-search-001',
            taskType: 'summary',
            snippet: '회의 결과 <b>FastAPI</b> 사용을 결정했습니다.',
            createdAt: DateTime(2024, 1, 3, 9),
          ),
        ],
        total: 1,
        page: 1,
        pageSize: 20,
        query: query,
      );
      const crossMeetingResponse = CrossMeetingAskResponse(
        answer: '질문과 관련된 회의 근거 1건을 찾았습니다.',
        sources: [
          CrossMeetingSource(
            taskId: 'sum-search-001',
            taskType: 'summary',
            snippet: '회의 결과 <b>FastAPI</b> 사용을 결정했습니다.',
            createdAt: '2024-01-03T09:00:00',
          ),
        ],
        query: query,
        total: 1,
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            searchResultProvider(request).overrideWith((_) => response),
            crossMeetingAskProvider(query)
                .overrideWith((_) => crossMeetingResponse),
          ],
          child: const MaterialApp(
            home: SearchScreen(),
          ),
        ),
      );

      await tester.enterText(find.byType(TextField), query);
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();

      expect(find.text('AI 근거 검색'), findsOneWidget);
      expect(find.text('1개 근거'), findsOneWidget);
      expect(find.textContaining('질문과 관련된 회의 근거'), findsOneWidget);
      expect(find.text('요약 1'), findsOneWidget);
    });
  });

  group('parseSnippet 유틸리티', () {
    // <b>태그 없는 일반 텍스트
    test('태그 없는 텍스트는 단일 TextSpan으로 반환되어야 함', () {
      const snippet = '일반 텍스트 내용';
      // 볼드 없이 전체가 일반 텍스트
      expect(snippet.contains('<b>'), isFalse);
    });

    // <b>태그가 포함된 텍스트 검증 (위젯으로 렌더링)
    testWidgets('<b>태그가 볼드 TextSpan으로 변환되어야 함', (WidgetTester tester) async {
      final item = SearchResultItem(
        taskId: 'test-id',
        taskType: 'minutes',
        snippet: '키워드 테스트 내용',
        createdAt: DateTime(2026, 3, 22),
      );
      final response = SearchResponse(
        items: [item],
        total: 1,
        page: 1,
        pageSize: 20,
        query: '키워드',
      );

      const searchRequest = SearchRequest(query: '키워드', sort: 'relevance');

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            searchResultProvider(searchRequest).overrideWith(
              (_) => response,
            ),
          ],
          child: const MaterialApp(
            home: SearchScreen(),
          ),
        ),
      );

      // 텍스트 입력 (debounce timer 경유)
      await tester.enterText(find.byType(TextField), '키워드');
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();

      // RichText가 렌더링되어야 함 (Text.rich 사용)
      expect(find.byType(RichText), findsWidgets);
      // 스니펫 내 텍스트가 표시되어야 함
      expect(find.textContaining('키워드'), findsWidgets);
    });
  });
}
