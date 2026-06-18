// ToneTimeline 위젯 테스트 - SPEC-TONE-001 REQ-TONE-012/013
// @MX:SPEC: SPEC-TONE-001
// 패턴 매칭: error_retry_widget_test.dart (MaterialApp+Scaffold 래핑)
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/tone_model.dart';
import 'package:voice_to_textnote/providers/result_provider.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';
import 'package:voice_to_textnote/widgets/error_retry_widget.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/widgets/tone_timeline.dart';

ToneResponse _sampleResponse({List<ToneSegment>? segments}) {
  return ToneResponse(
    taskId: 'tone-001',
    status: 'completed',
    segments: segments ??
        [
          const ToneSegment(
            start: 0.0,
            end: 2.5,
            speaker: 'SPEAKER_00',
            tone: 'calm',
            confidence: 0.82,
            prosodyFeatures: {},
          ),
          const ToneSegment(
            start: 2.5,
            end: 5.0,
            speaker: 'SPEAKER_01',
            tone: 'excited',
            confidence: 0.91,
            prosodyFeatures: {},
          ),
        ],
    speakers: const [
      SpeakerTone(
        speaker: 'SPEAKER_00',
        dominantTone: 'calm',
        toneDistribution: {'calm': 5.0},
        avgPitch: 118.3,
        avgEnergy: 0.042,
      ),
    ],
    overallTone: 'calm',
  );
}

void main() {
  group('toneColor', () {
    test('톤별 올바른 색상 반환 (REQ-TONE-012 색상 계약)', () {
      expect(toneColor('calm'), AppColors.indigo500);
      expect(toneColor('excited'), AppColors.warning);
      expect(toneColor('authoritative'), AppColors.violet500);
      expect(toneColor('hesitant'), const Color(0xFFF97316));
      expect(toneColor('monotone'), const Color(0xFF9CA3AF));
      expect(toneColor('unknown'), AppColors.lightTextTertiary);
    });

    test('알 수 없는 톤은 unknown 색상으로 폴백', () {
      expect(toneColor('invalid_tone'), AppColors.lightTextTertiary);
    });
  });

  group('ToneTimeline 렌더링', () {
    // REQ-TONE-012: 세그먼트 렌더링
    testWidgets('세그먼트가 화자 및 톤 정보와 함께 렌더링되어야 함', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ToneTimeline(response: _sampleResponse()),
          ),
        ),
      );

      expect(find.text('톤 타임라인'), findsOneWidget);
      expect(find.text('SPEAKER_00'), findsOneWidget);
      expect(find.text('SPEAKER_01'), findsOneWidget);
    });

    testWidgets('빈 세그먼트 응답도 카드 제목은 렌더링됨', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ToneTimeline(response: _sampleResponse(segments: [])),
          ),
        ),
      );

      expect(find.text('톤 타임라인'), findsOneWidget);
    });
  });

  group('ToneSection 상태별 렌더링 (REQ-TONE-012)', () {
    // REQ-TONE-012: 로딩 상태
    testWidgets('로딩 상태: CircularProgressIndicator 표시', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            toneProvider('meeting-001').overrideWith(
              (ref) => Completer<ToneResponse>().future,
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: ToneSection(meetingId: 'meeting-001'),
            ),
          ),
        ),
      );

      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    // REQ-TONE-013: 에러 상태 (SizedBox.shrink 금지)
    testWidgets('에러 상태: ErrorRetryWidget + 재시도 버튼 표시 (silent failure 금지)',
        (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            toneProvider('meeting-001').overrideWith(
              (ref) async => throw Exception('톤 API 오류'),
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: ToneSection(meetingId: 'meeting-001'),
            ),
          ),
        ),
      );

      // 에러 상태로 전환 대기
      await tester.pump();
      await tester.pump();

      expect(find.byType(ErrorRetryWidget), findsOneWidget);
      expect(find.text('톤 분석을 불러올 수 없습니다'), findsOneWidget);
      expect(find.text('다시 시도'), findsOneWidget);
    });

    // REQ-TONE-012: 빈 데이터 상태
    testWidgets('빈 데이터 상태: EmptyStateWidget 표시', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            toneProvider('meeting-001').overrideWith(
              (ref) async => const ToneResponse(
                taskId: 'empty',
                status: 'skipped',
                segments: [],
                speakers: [],
                overallTone: 'unknown',
              ),
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: ToneSection(meetingId: 'meeting-001'),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(EmptyStateWidget), findsOneWidget);
      expect(find.text('톤 분석 데이터가 없습니다'), findsOneWidget);
    });

    // REQ-TONE-012: 데이터 정상 렌더링
    testWidgets('데이터 상태: ToneTimeline + 화자 요약 렌더링', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            toneProvider('meeting-001').overrideWith(
              (ref) async => _sampleResponse(),
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: ToneSection(meetingId: 'meeting-001'),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(ToneTimeline), findsOneWidget);
      // SPEAKER_00은 화자 요약 카드 + 타임라인에 각각 표시됨 (2회)
      expect(find.text('SPEAKER_00'), findsNWidgets(2));
      expect(find.text('화자별 톤 요약'), findsOneWidget);
    });
  });

  // REQ-TONE-013 핵심: 오류 격리 - tone 실패 시 sentiment 위젯 영향 없음
  testWidgets('ToneSection 에러 시 다른 위젯 렌더링에 영향을 주지 않아야 함 (오류 격리)',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          toneProvider('meeting-001').overrideWith(
            (ref) async => throw Exception('톤 API 실패'),
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                Text('감정 분석 카드 (정상)'),
                ToneSection(meetingId: 'meeting-001'),
              ],
            ),
          ),
        ),
      ),
    );

    await tester.pump();
    await tester.pump();

    // sentiment 카드는 여전히 렌더링됨 (오류 격리)
    expect(find.text('감정 분석 카드 (정상)'), findsOneWidget);
    // tone 섹션은 에러 위젯 표시 (silent failure 아님)
    expect(find.byType(ErrorRetryWidget), findsOneWidget);
  });
}
