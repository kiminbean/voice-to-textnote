// RecordingProvider 상태 관리 테스트
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/providers/recording_provider.dart';

void main() {
  group('RecordingProvider', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
    });

    // 초기 상태 테스트
    test('초기 상태는 idle이어야 함', () {
      final state = container.read(recordingProvider);

      expect(state.status, RecordingStatus.idle);
      expect(state.elapsedSeconds, 0);
      expect(state.filePath, isNull);
    });

    // 녹음 시작 상태 전환 테스트
    test('startRecording 호출 시 상태가 recording으로 변경되어야 함', () {
      container.read(recordingProvider.notifier).startRecording();
      final state = container.read(recordingProvider);

      expect(state.status, RecordingStatus.recording);
    });

    // 녹음 중지 상태 전환 테스트
    test('stopRecording 호출 시 상태가 stopped로 변경되어야 함', () {
      // 녹음 시작 후 중지
      container.read(recordingProvider.notifier).startRecording();
      container.read(recordingProvider.notifier).stopRecording();
      final state = container.read(recordingProvider);

      expect(state.status, RecordingStatus.stopped);
    });

    // 리셋 테스트
    test('reset 호출 시 초기 상태로 돌아가야 함', () {
      // 녹음 후 리셋
      container.read(recordingProvider.notifier).startRecording();
      container.read(recordingProvider.notifier).stopRecording();
      container.read(recordingProvider.notifier).reset();

      final state = container.read(recordingProvider);

      expect(state.status, RecordingStatus.idle);
      expect(state.elapsedSeconds, 0);
      expect(state.filePath, isNull);
    });

    // RecordingStatus 열거형 테스트
    test('모든 RecordingStatus 값이 존재해야 함', () {
      expect(RecordingStatus.values, containsAll([
        RecordingStatus.idle,
        RecordingStatus.recording,
        RecordingStatus.paused,
        RecordingStatus.stopped,
      ]));
    });
  });
}
