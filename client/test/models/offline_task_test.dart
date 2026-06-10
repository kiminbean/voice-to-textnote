import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/offline_task.dart';

void main() {
  group('OfflineTask', () {
    test('creates task with pending status', () {
      final task = OfflineTask(
        id: 'task-1',
        audioPath: '/audio/test.wav',
        offlineTranscriptionPath: '/transcription/offline.json',
        status: OfflineTaskStatus.pending,
        createdAt: DateTime(2026, 1, 1),
      );

      expect(task.id, 'task-1');
      expect(task.status, OfflineTaskStatus.pending);
      expect(task.onlineTranscriptionTaskId, isNull);
      expect(task.reprocessedAt, isNull);
      expect(task.errorMessage, isNull);
    });

    test('creates task with reprocessing status', () {
      final task = OfflineTask(
        id: 'task-2',
        audioPath: '/audio/test.wav',
        offlineTranscriptionPath: '/transcription/offline.json',
        onlineTranscriptionTaskId: 'online-task-123',
        status: OfflineTaskStatus.reprocessing,
        createdAt: DateTime(2026, 1, 1),
      );

      expect(task.status, OfflineTaskStatus.reprocessing);
      expect(task.onlineTranscriptionTaskId, 'online-task-123');
    });

    test('creates task with completed status', () {
      final task = OfflineTask(
        id: 'task-3',
        audioPath: '/audio/test.wav',
        offlineTranscriptionPath: '/transcription/offline.json',
        onlineTranscriptionTaskId: 'online-task-123',
        status: OfflineTaskStatus.completed,
        createdAt: DateTime(2026, 1, 1),
        reprocessedAt: DateTime(2026, 1, 2),
      );

      expect(task.status, OfflineTaskStatus.completed);
      expect(task.reprocessedAt, DateTime(2026, 1, 2));
    });

    test('creates task with failed status', () {
      final task = OfflineTask(
        id: 'task-4',
        audioPath: '/audio/test.wav',
        offlineTranscriptionPath: '/transcription/offline.json',
        status: OfflineTaskStatus.failed,
        createdAt: DateTime(2026, 1, 1),
        errorMessage: 'Network timeout',
      );

      expect(task.status, OfflineTaskStatus.failed);
      expect(task.errorMessage, 'Network timeout');
    });

    test('copyWith updates specified fields', () {
      final original = OfflineTask(
        id: 'task-1',
        audioPath: '/audio/test.wav',
        offlineTranscriptionPath: '/transcription/offline.json',
        status: OfflineTaskStatus.pending,
        createdAt: DateTime(2026, 1, 1),
      );

      final updated = original.copyWith(
        status: OfflineTaskStatus.reprocessing,
        onlineTranscriptionTaskId: 'online-task-123',
      );

      expect(updated.id, original.id);
      expect(updated.audioPath, original.audioPath);
      expect(updated.status, OfflineTaskStatus.reprocessing);
      expect(updated.onlineTranscriptionTaskId, 'online-task-123');
      expect(
          updated.offlineTranscriptionPath, original.offlineTranscriptionPath);
    });

    test('fromJson creates task from JSON', () {
      final json = {
        'id': 'task-1',
        'audio_path': '/audio/test.wav',
        'offline_transcription_path': '/transcription/offline.json',
        'online_transcription_task_id': 'online-task-123',
        'status': 'reprocessing',
        'created_at': '2026-01-01T00:00:00.000Z',
        'reprocessed_at': '2026-01-02T00:00:00.000Z',
        'error_message': 'Network error',
      };

      final task = OfflineTask.fromJson(json);

      expect(task.id, 'task-1');
      expect(task.audioPath, '/audio/test.wav');
      expect(task.offlineTranscriptionPath, '/transcription/offline.json');
      expect(task.onlineTranscriptionTaskId, 'online-task-123');
      expect(task.status, OfflineTaskStatus.reprocessing);
      expect(task.reprocessedAt, DateTime.utc(2026, 1, 2));
      expect(task.errorMessage, 'Network error');
    });

    test('toJson serializes task to JSON', () {
      final task = OfflineTask(
        id: 'task-1',
        audioPath: '/audio/test.wav',
        offlineTranscriptionPath: '/transcription/offline.json',
        onlineTranscriptionTaskId: 'online-task-123',
        status: OfflineTaskStatus.reprocessing,
        createdAt: DateTime.utc(2026, 1, 1),
        reprocessedAt: DateTime.utc(2026, 1, 2),
        errorMessage: 'Network error',
      );

      final json = task.toJson();

      expect(json['id'], 'task-1');
      expect(json['audio_path'], '/audio/test.wav');
      expect(json['offline_transcription_path'], '/transcription/offline.json');
      expect(json['online_transcription_task_id'], 'online-task-123');
      expect(json['status'], 'reprocessing');
      expect(json['created_at'], '2026-01-01T00:00:00.000Z');
      expect(json['reprocessed_at'], '2026-01-02T00:00:00.000Z');
      expect(json['error_message'], 'Network error');
    });

    test('JSON round-trip preserves data', () {
      final original = OfflineTask(
        id: 'task-1',
        audioPath: '/audio/test.wav',
        offlineTranscriptionPath: '/transcription/offline.json',
        onlineTranscriptionTaskId: 'online-task-123',
        status: OfflineTaskStatus.completed,
        createdAt: DateTime.utc(2026, 1, 1),
        reprocessedAt: DateTime.utc(2026, 1, 2),
        errorMessage: 'Network error',
      );

      final json = original.toJson();
      final restored = OfflineTask.fromJson(json);

      expect(restored.id, original.id);
      expect(restored.audioPath, original.audioPath);
      expect(
          restored.offlineTranscriptionPath, original.offlineTranscriptionPath);
      expect(restored.onlineTranscriptionTaskId,
          original.onlineTranscriptionTaskId);
      expect(restored.status, original.status);
      expect(restored.createdAt, original.createdAt);
      expect(restored.reprocessedAt, original.reprocessedAt);
      expect(restored.errorMessage, original.errorMessage);
    });
  });

  group('OfflineTaskStatus', () {
    test('status enum values are correct', () {
      expect(OfflineTaskStatus.pending, isA<OfflineTaskStatus>());
      expect(OfflineTaskStatus.reprocessing, isA<OfflineTaskStatus>());
      expect(OfflineTaskStatus.completed, isA<OfflineTaskStatus>());
      expect(OfflineTaskStatus.failed, isA<OfflineTaskStatus>());
    });
  });
}
