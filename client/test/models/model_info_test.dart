import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/models/model_info.dart';

void main() {
  group('ModelStatus', () {
    test('notDownloaded 상태 생성', () {
      const status = ModelStatus.notDownloaded();

      expect(status, isA<ModelStatus>());
      expect(status.toString(), contains('notDownloaded'));
    });

    test('downloading 상태 생성 (progress 포함)', () {
      const status = ModelStatus.downloading(0.5);

      expect(status, isA<ModelStatus>());
      expect(status.toString(), contains('downloading'));
      expect(status.toString(), contains('0.5'));
    });

    test('downloaded 상태 생성', () {
      const status = ModelStatus.downloaded();

      expect(status, isA<ModelStatus>());
      expect(status.toString(), contains('downloaded'));
    });

    test('verified 상태 생성', () {
      const status = ModelStatus.verified();

      expect(status, isA<ModelStatus>());
      expect(status.toString(), contains('verified'));
    });

    test('error 상태 생성 (message 포함)', () {
      const status = ModelStatus.error('다운로드 실패');

      expect(status, isA<ModelStatus>());
      expect(status.toString(), contains('error'));
      expect(status.toString(), contains('다운로드 실패'));
    });

    test('상태 전이: notDownloaded → downloading → downloaded → verified', () {
      // 시작: 다운로드 안 됨
      const status1 = ModelStatus.notDownloaded();

      // 다운로드 시작
      const status2 = ModelStatus.downloading(0.3);
      expect(status2, isNot(equals(status1)));

      // 다운로드 완료
      const status3 = ModelStatus.downloaded();
      expect(status3, isNot(equals(status2)));

      // 검증 완료
      const status4 = ModelStatus.verified();
      expect(status4, isNot(equals(status3)));
    });

    test('상태 전이: downloading → error', () {
      const status1 = ModelStatus.downloading(0.5);
      const status2 = ModelStatus.error('네트워크 오류');

      expect(status2, isNot(equals(status1)));
    });
  });

  group('ModelInfo', () {
    test('기본 ModelInfo 생성', () {
      const info = ModelInfo(
        modelId: 'whisper-base',
        version: '1.0.0',
        sizeBytes: 150000000,
        expectedChecksum: 'abc123',
        status: ModelStatus.notDownloaded(),
      );

      expect(info.modelId, 'whisper-base');
      expect(info.version, '1.0.0');
      expect(info.sizeBytes, 150000000);
      expect(info.expectedChecksum, 'abc123');
      expect(info.status, isA<ModelStatus>());
      expect(info.localPath, isNull);
      expect(info.downloadedAt, isNull);
      expect(info.downloadUrl, isNull);
    });

    test('다운로드 완료된 ModelInfo 생성', () {
      final now = DateTime(2025, 1, 10);
      final info = ModelInfo(
        modelId: 'whisper-base',
        version: '1.0.0',
        sizeBytes: 150000000,
        expectedChecksum: 'abc123',
        status: ModelStatus.downloaded(),
        localPath: '/path/to/model',
        downloadedAt: now,
        downloadUrl: 'https://example.com/model',
      );

      expect(info.localPath, '/path/to/model');
      expect(info.downloadedAt, now);
      expect(info.downloadUrl, 'https://example.com/model');
    });

    test('copyWith - 모든 필드 업데이트', () {
      final now1 = DateTime(2025, 1, 10);
      final now2 = DateTime(2025, 1, 11);

      final info1 = ModelInfo(
        modelId: 'whisper-base',
        version: '1.0.0',
        sizeBytes: 150000000,
        expectedChecksum: 'abc123',
        status: ModelStatus.notDownloaded(),
        downloadedAt: now1,
      );

      final info2 = info1.copyWith(
        modelId: 'whisper-large',
        version: '2.0.0',
        sizeBytes: 300000000,
        expectedChecksum: 'def456',
        status: ModelStatus.downloaded(),
        localPath: '/new/path',
        downloadedAt: now2,
        downloadUrl: 'https://example.com/new',
      );

      expect(info2.modelId, 'whisper-large');
      expect(info2.version, '2.0.0');
      expect(info2.sizeBytes, 300000000);
      expect(info2.expectedChecksum, 'def456');
      expect(info2.status, isA<ModelStatus>());
      expect(info2.localPath, '/new/path');
      expect(info2.downloadedAt, now2);
      expect(info2.downloadUrl, 'https://example.com/new');
    });

    test('copyWith - 부분 필드 업데이트', () {
      const info1 = ModelInfo(
        modelId: 'whisper-base',
        version: '1.0.0',
        sizeBytes: 150000000,
        expectedChecksum: 'abc123',
        status: ModelStatus.notDownloaded(),
      );

      final info2 = info1.copyWith(
        status: ModelStatus.downloading(0.5),
      );

      expect(info2.modelId, 'whisper-base'); // unchanged
      expect(info2.version, '1.0.0'); // unchanged
      expect(info2.status, isA<ModelStatus>());
    });

    test('copyWith - nullable 필드를 null로 설정', () {
      final info1 = ModelInfo(
        modelId: 'whisper-base',
        version: '1.0.0',
        sizeBytes: 150000000,
        expectedChecksum: 'abc123',
        status: ModelStatus.downloaded(),
        localPath: '/path/to/model',
        downloadedAt: DateTime(2025, 1, 10),
        downloadUrl: 'https://example.com/model',
      );

      final info2 = info1.copyWith(
        clearLocalPath: true,
        clearDownloadedAt: true,
        clearDownloadUrl: true,
      );

      expect(info2.localPath, isNull);
      expect(info2.downloadedAt, isNull);
      expect(info2.downloadUrl, isNull);
    });

    test('fromJson - 기본 ModelInfo', () {
      final json = {
        'modelId': 'whisper-base',
        'version': '1.0.0',
        'sizeBytes': 150000000,
        'expectedChecksum': 'abc123',
        'status': 'notDownloaded',
      };

      final info = ModelInfo.fromJson(json);

      expect(info.modelId, 'whisper-base');
      expect(info.version, '1.0.0');
      expect(info.sizeBytes, 150000000);
      expect(info.expectedChecksum, 'abc123');
      expect(info.status, ModelStatus.notDownloaded());
    });

    test('fromJson - 다운로드 완료된 ModelInfo', () {
      final json = {
        'modelId': 'whisper-base',
        'version': '1.0.0',
        'sizeBytes': 150000000,
        'expectedChecksum': 'abc123',
        'status': 'verified',
        'localPath': '/path/to/model',
        'downloadedAt': '2025-01-10T00:00:00.000Z',
        'downloadUrl': 'https://example.com/model',
      };

      final info = ModelInfo.fromJson(json);

      expect(info.status, ModelStatus.verified());
      expect(info.localPath, '/path/to/model');
      expect(info.downloadedAt, DateTime.parse('2025-01-10T00:00:00.000Z'));
      expect(info.downloadUrl, 'https://example.com/model');
    });

    test('fromJson - downloading 상태 (progress 포함)', () {
      final json = {
        'modelId': 'whisper-base',
        'version': '1.0.0',
        'sizeBytes': 150000000,
        'expectedChecksum': 'abc123',
        'status': 'downloading',
        'progress': 0.75,
      };

      final info = ModelInfo.fromJson(json);

      expect(info.status, ModelStatus.downloading(0.75));
    });

    test('fromJson - error 상태 (message 포함)', () {
      final json = {
        'modelId': 'whisper-base',
        'version': '1.0.0',
        'sizeBytes': 150000000,
        'expectedChecksum': 'abc123',
        'status': 'error',
        'errorMessage': '디스크 공간 부족',
      };

      final info = ModelInfo.fromJson(json);

      expect(info.status, ModelStatus.error('디스크 공간 부족'));
    });

    test('toJson - 기본 ModelInfo', () {
      const info = ModelInfo(
        modelId: 'whisper-base',
        version: '1.0.0',
        sizeBytes: 150000000,
        expectedChecksum: 'abc123',
        status: ModelStatus.notDownloaded(),
      );

      final json = info.toJson();

      expect(json['modelId'], 'whisper-base');
      expect(json['version'], '1.0.0');
      expect(json['sizeBytes'], 150000000);
      expect(json['expectedChecksum'], 'abc123');
      expect(json['status'], 'notDownloaded');
    });

    test('toJson - 다운로드 완료된 ModelInfo', () {
      final now = DateTime(2025, 1, 10);
      final info = ModelInfo(
        modelId: 'whisper-base',
        version: '1.0.0',
        sizeBytes: 150000000,
        expectedChecksum: 'abc123',
        status: ModelStatus.verified(),
        localPath: '/path/to/model',
        downloadedAt: now,
        downloadUrl: 'https://example.com/model',
      );

      final json = info.toJson();

      expect(json['status'], 'verified');
      expect(json['localPath'], '/path/to/model');
      expect(json['downloadedAt'], '2025-01-10T00:00:00.000Z');
      expect(json['downloadUrl'], 'https://example.com/model');
    });

    test('toJson - downloading 상태', () {
      const info = ModelInfo(
        modelId: 'whisper-base',
        version: '1.0.0',
        sizeBytes: 150000000,
        expectedChecksum: 'abc123',
        status: ModelStatus.downloading(0.6),
      );

      final json = info.toJson();

      expect(json['status'], 'downloading');
      expect(json['progress'], 0.6);
    });

    test('toJson - error 상태', () {
      const info = ModelInfo(
        modelId: 'whisper-base',
        version: '1.0.0',
        sizeBytes: 150000000,
        expectedChecksum: 'abc123',
        status: ModelStatus.error('네트워크 오류'),
      );

      final json = info.toJson();

      expect(json['status'], 'error');
      expect(json['errorMessage'], '네트워크 오류');
    });

    test('fromJson → toJson round-trip', () {
      final json1 = {
        'modelId': 'whisper-large',
        'version': '2.0.0',
        'sizeBytes': 300000000,
        'expectedChecksum': 'def456',
        'status': 'verified',
        'localPath': '/models/large',
        'downloadedAt': '2025-01-10T12:30:00.000Z',
        'downloadUrl': 'https://example.com/large',
      };

      final info = ModelInfo.fromJson(json1);
      final json2 = info.toJson();

      expect(json2['modelId'], json1['modelId']);
      expect(json2['version'], json1['version']);
      expect(json2['sizeBytes'], json1['sizeBytes']);
      expect(json2['expectedChecksum'], json1['expectedChecksum']);
      expect(json2['status'], json1['status']);
      expect(json2['localPath'], json1['localPath']);
      expect(json2['downloadedAt'], json1['downloadedAt']);
      expect(json2['downloadUrl'], json1['downloadUrl']);
    });
  });
}
