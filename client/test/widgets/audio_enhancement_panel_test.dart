import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/widgets/audio_enhancement_panel.dart';

void main() {
  testWidgets('오디오 향상 설정은 버튼을 누른 뒤 bottom sheet로 열린다', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: AudioEnhancementLauncher(audioFilePath: '/tmp/meeting.wav'),
          ),
        ),
      ),
    );

    expect(find.byType(AudioEnhancementPanel), findsNothing);
    expect(find.text('오디오 향상'), findsOneWidget);

    await tester.tap(find.text('오디오 향상'));
    await tester.pumpAndSettle();

    expect(find.byType(AudioEnhancementPanel), findsOneWidget);
    expect(find.text('음성만'), findsOneWidget);
  });
}
