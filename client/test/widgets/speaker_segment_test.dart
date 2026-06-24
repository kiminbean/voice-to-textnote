import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/widgets/speaker_segment.dart';

void main() {
  testWidgets('발화 시작/종료 시간이 구간으로 표시되어야 함', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SpeakerSegment(
            speakerName: 'Speaker 1',
            text: '회의 내용입니다.',
            startTime: Duration(milliseconds: 300),
            endTime: Duration(milliseconds: 61780),
          ),
        ),
      ),
    );

    expect(find.text('Speaker 1'), findsOneWidget);
    expect(find.text('0:00 - 1:01'), findsOneWidget);
    expect(find.text('0:00'), findsNothing);
  });

  testWidgets('종료 시간이 없으면 기존처럼 시작 시간만 표시해야 함', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SpeakerSegment(
            speakerName: 'Speaker 1',
            text: '회의 내용입니다.',
            startTime: Duration(seconds: 12),
          ),
        ),
      ),
    );

    expect(find.text('0:12'), findsOneWidget);
  });
}
