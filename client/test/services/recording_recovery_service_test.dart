// SPEC-MOBILE-004 T-009/T-010: 녹음 복원 서비스 테스트
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/services/recording_recovery_service.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('RecordingRecoveryService', () {
    test('saveActiveRecording stores filePath and startedAt', () async {
      final service = RecordingRecoveryService();
      await service.saveActiveRecording(
        '/path/to/recording.m4a',
        startedAt: '2026-06-13T10:00:00Z',
      );

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('active_recording_path'), '/path/to/recording.m4a');
      expect(prefs.getString('active_recording_started_at'), '2026-06-13T10:00:00Z');
    });

    test('getActiveRecordingPath returns saved path', () async {
      final service = RecordingRecoveryService();
      await service.saveActiveRecording(
        '/path/to/meeting.m4a',
        startedAt: '2026-06-13T10:00:00Z',
      );

      expect(await service.getActiveRecordingPath(), '/path/to/meeting.m4a');
    });

    test('getActiveRecordingStartedAt returns saved timestamp', () async {
      final service = RecordingRecoveryService();
      await service.saveActiveRecording(
        '/path/to/meeting.m4a',
        startedAt: '2026-06-13T10:00:00Z',
      );

      expect(await service.getActiveRecordingStartedAt(), '2026-06-13T10:00:00Z');
    });

    test('hasActiveRecording returns true when path exists', () async {
      final service = RecordingRecoveryService();
      await service.saveActiveRecording(
        '/path/to/meeting.m4a',
        startedAt: '2026-06-13T10:00:00Z',
      );

      expect(await service.hasActiveRecording(), isTrue);
    });

    test('hasActiveRecording returns false when no path', () async {
      final service = RecordingRecoveryService();
      expect(await service.hasActiveRecording(), isFalse);
    });

    test('clearActiveRecording removes saved data', () async {
      final service = RecordingRecoveryService();
      await service.saveActiveRecording(
        '/path/to/meeting.m4a',
        startedAt: '2026-06-13T10:00:00Z',
      );

      await service.clearActiveRecording();

      expect(await service.hasActiveRecording(), isFalse);
      expect(await service.getActiveRecordingPath(), isNull);
    });
  });
}
