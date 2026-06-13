// RecordingProvider 상태 관리 테스트
// SPEC-MOBILE-005: 인터럽션 상태 전이 검증 추가 (REQ-002)
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/providers/recording_provider.dart';

void main() {
  // MethodChannel 사용을 위해 바인딩 초기화
  TestWidgetsFlutterBinding.ensureInitialized();

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

    // 리셋 테스트
    test('reset 호출 시 초기 상태로 돌아가야 함', () {
      // 수동으로 상태 변경 후 리셋
      container.read(recordingProvider.notifier).updateElapsedSeconds(30);
      container.read(recordingProvider.notifier).setFilePath('/tmp/test.m4a');
      container.read(recordingProvider.notifier).reset();

      final state = container.read(recordingProvider);

      expect(state.status, RecordingStatus.idle);
      expect(state.elapsedSeconds, 0);
      expect(state.filePath, isNull);
    });

    // 경과 시간 업데이트 테스트
    test('updateElapsedSeconds 호출 시 경과 시간이 변경되어야 함', () {
      container.read(recordingProvider.notifier).updateElapsedSeconds(42);
      final state = container.read(recordingProvider);
      expect(state.elapsedSeconds, 42);
    });

    // 파일 경로 설정 테스트
    test('setFilePath 호출 시 파일 경로가 설정되어야 함', () {
      const testPath = '/test/path/meeting.m4a';
      container.read(recordingProvider.notifier).setFilePath(testPath);
      final state = container.read(recordingProvider);
      expect(state.filePath, testPath);
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

    // RecordingState copyWith 테스트
    test('RecordingState copyWith가 올바르게 동작해야 함', () {
      const original = RecordingState(
        status: RecordingStatus.idle,
        elapsedSeconds: 0,
      );

      final updated = original.copyWith(
        status: RecordingStatus.recording,
        elapsedSeconds: 10,
        filePath: '/test/file.m4a',
      );

      expect(updated.status, RecordingStatus.recording);
      expect(updated.elapsedSeconds, 10);
      expect(updated.filePath, '/test/file.m4a');
      // 원본은 변경되지 않아야 함
      expect(original.status, RecordingStatus.idle);
      expect(original.elapsedSeconds, 0);
      expect(original.filePath, isNull);
    });

    // copyWith 일부 필드만 변경 테스트
    test('RecordingState copyWith 일부 필드만 변경 시 나머지는 유지되어야 함', () {
      const original = RecordingState(
        status: RecordingStatus.recording,
        elapsedSeconds: 15,
        filePath: '/test/file.m4a',
      );

      final updated = original.copyWith(elapsedSeconds: 20);

      expect(updated.status, RecordingStatus.recording);
      expect(updated.elapsedSeconds, 20);
      expect(updated.filePath, '/test/file.m4a');
    });
  });

  // SPEC-MOBILE-005 REQ-002: 인터럽션 상태 검증
  group('REQ-002: 인터럽션 상태 관리', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
    });

    test('초기 상태에서 interruptionStatus는 none이어야 함', () {
      final state = container.read(recordingProvider);
      expect(state.interruptionStatus, InterruptionStatus.none);
    });

    test('InterruptionStatus 열거형에 none과 interrupted가 존재해야 함', () {
      expect(InterruptionStatus.values, contains(InterruptionStatus.none));
      expect(InterruptionStatus.values, contains(InterruptionStatus.interrupted));
    });

    test('RecordingState copyWith로 interruptionStatus를 변경할 수 있어야 함', () {
      const original = RecordingState(
        status: RecordingStatus.recording,
        elapsedSeconds: 10,
      );

      final updated = original.copyWith(
        status: RecordingStatus.paused,
        interruptionStatus: InterruptionStatus.interrupted,
      );

      expect(updated.status, RecordingStatus.paused);
      expect(updated.interruptionStatus, InterruptionStatus.interrupted);
      // 원본은 변경되지 않아야 함
      expect(original.interruptionStatus, InterruptionStatus.none);
    });

    test('interruptionStatus 기본값은 none이어야 함', () {
      const state = RecordingState(
        status: RecordingStatus.idle,
        elapsedSeconds: 0,
      );
      expect(state.interruptionStatus, InterruptionStatus.none);
    });

    test('reset 호출 시 interruptionStatus도 none으로 초기화되어야 함', () {
      container.read(recordingProvider.notifier).updateElapsedSeconds(30);
      container.read(recordingProvider.notifier).reset();

      final state = container.read(recordingProvider);
      expect(state.interruptionStatus, InterruptionStatus.none);
    });
  });
}
