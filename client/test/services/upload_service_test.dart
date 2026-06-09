// UploadService 및 ChunkUploadProgress 테스트
// SPEC-APP-005 REQ-013,014 — 50MB 초과 파일 10MB 청크 분할 순차 업로드
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/services/upload_service.dart';

void main() {
  group('ChunkUploadProgress', () {
    test('생성 시 필드값이 올바르게 설정되어야 함', () {
      // Act
      const progress = ChunkUploadProgress(
        totalChunks: 5,
        completedChunks: 2,
        currentChunk: 2,
        progress: 0.4,
      );

      // Assert
      expect(progress.totalChunks, 5);
      expect(progress.completedChunks, 2);
      expect(progress.currentChunk, 2);
      expect(progress.progress, 0.4);
    });

    test('isComplete — 모든 청크 완료 시 true여야 함', () {
      // Arrange
      const progress = ChunkUploadProgress(
        totalChunks: 3,
        completedChunks: 3,
        currentChunk: 2,
        progress: 1.0,
      );

      // Act & Assert
      expect(progress.isComplete, true);
    });

    test('isComplete — 일부 청크만 완료 시 false여야 함', () {
      // Arrange
      const progress = ChunkUploadProgress(
        totalChunks: 5,
        completedChunks: 3,
        currentChunk: 3,
        progress: 0.6,
      );

      // Act & Assert
      expect(progress.isComplete, false);
    });

    test('isComplete — completedChunks가 totalChunks보다 크면 true여야 함', () {
      // Arrange
      const progress = ChunkUploadProgress(
        totalChunks: 2,
        completedChunks: 3,
        currentChunk: 2,
        progress: 1.0,
      );

      // Act & Assert
      expect(progress.isComplete, true);
    });
  });

  group('UploadService', () {
    test('chunkSize 상수는 10MB(10485760)이어야 함', () {
      // Assert
      expect(UploadService.chunkSize, 10 * 1024 * 1024);
    });

    test('largeFileThreshold 상수는 50MB(52428800)이어야 함', () {
      // Assert
      expect(UploadService.largeFileThreshold, 50 * 1024 * 1024);
    });

    test('shouldUseChunkUpload() — 존재하지 않는 파일은 false를 반환해야 함', () {
      // Arrange
      final service = UploadService();

      // Act
      final result = service.shouldUseChunkUpload('/nonexistent/path/file.m4a');

      // Assert
      expect(result, false);
    });

    test('shouldUseChunkUpload() — 작은 파일은 false를 반환해야 함', () async {
      // Arrange: 임시 파일 생성 (1KB)
      final tempDir = await Directory.systemTemp.createTemp('upload_test_');
      final smallFile = File('${tempDir.path}/small.m4a');
      await smallFile.writeAsBytes(List.filled(1024, 0));

      final service = UploadService();

      // Act
      final result = service.shouldUseChunkUpload(smallFile.path);

      // Assert
      expect(result, false);

      // Cleanup
      await tempDir.delete(recursive: true);
    });

    test('shouldUseChunkUpload() — 50MB 초과 파일은 true를 반환해야 함', () async {
      // Arrange: 51MB 임시 파일 생성
      final tempDir = await Directory.systemTemp.createTemp('upload_test_');
      final largeFile = File('${tempDir.path}/large.m4a');
      // 51MB = 50 * 1024 * 1024 + 1 byte
      final largeSize = 50 * 1024 * 1024 + 1;
      await largeFile.writeAsBytes(List.filled(largeSize, 0));

      final service = UploadService();

      // Act
      final result = service.shouldUseChunkUpload(largeFile.path);

      // Assert
      expect(result, true);

      // Cleanup
      await tempDir.delete(recursive: true);
    });
  });
}
