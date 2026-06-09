// 청크 분할 업로드 서비스
// @MX:NOTE: SPEC-APP-005 REQ-013,014 — 50MB 초과 파일 10MB 청크 분할 순차 업로드

import 'dart:io';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:voice_to_textnote/config/app_config.dart';

/// 청크 업로드 진행 상태
class ChunkUploadProgress {
  final int totalChunks;
  final int completedChunks;
  final int currentChunk;
  final double progress; // 0.0 ~ 1.0

  const ChunkUploadProgress({
    required this.totalChunks,
    required this.completedChunks,
    required this.currentChunk,
    required this.progress,
  });

  bool get isComplete => completedChunks >= totalChunks;
}

/// 청크 분할 업로드 서비스 (REQ-013, REQ-014)
class UploadService {
  final Dio _dio;

  /// 청크 분할 기준 크기 (10MB)
  static const int chunkSize = 10 * 1024 * 1024;

  /// 대용량 파일 기준 (50MB 이상 시 청크 모드)
  static const int largeFileThreshold = 50 * 1024 * 1024;

  UploadService({Dio? dio}) : _dio = dio ?? Dio();

  /// 파일 크기에 따라 청크 모드 여부 결정
  bool shouldUseChunkUpload(String filePath) {
    final file = File(filePath);
    if (!file.existsSync()) return false;
    return file.lengthSync() > largeFileThreshold;
  }

  /// 파일 업로드 (자동 청크 분할)
  /// 파일이 50MB 초과 시 10MB 청크로 분할하여 순차 업로드 (REQ-013)
  Future<Map<String, dynamic>> upload(
    String filePath, {
    String? vocabularyId,
    void Function(ChunkUploadProgress)? onProgress,
  }) async {
    final file = File(filePath);
    if (!file.existsSync()) {
      throw Exception('파일을 찾을 수 없습니다: $filePath');
    }

    final fileSize = file.lengthSync();

    if (fileSize <= largeFileThreshold) {
      // 일반 업로드 (50MB 이하)
      return _singleUpload(file, vocabularyId: vocabularyId);
    }

    // 청크 업로드 (50MB 초과)
    return _chunkedUpload(file, vocabularyId: vocabularyId, onProgress: onProgress);
  }

  /// 일반 단일 업로드
  Future<Map<String, dynamic>> _singleUpload(
    File file, {
    String? vocabularyId,
  }) async {
    final fileName = file.path.split('/').last;
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(file.path, filename: fileName),
      if (vocabularyId != null) 'vocabulary_id': vocabularyId,
    });

    final response = await _dio.post(
      '${AppConfig.apiBaseUrl}/api/v1/transcriptions',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );

    return response.data as Map<String, dynamic>;
  }

  /// 청크 분할 업로드 (REQ-013)
  Future<Map<String, dynamic>> _chunkedUpload(
    File file, {
    String? vocabularyId,
    void Function(ChunkUploadProgress)? onProgress,
  }) async {
    final fileSize = file.lengthSync();
    final totalChunks = (fileSize / chunkSize).ceil();
    final fileName = file.path.split('/').last;
    final uploadId = 'upload_${DateTime.now().millisecondsSinceEpoch}';

    // 마지막 성공 청크부터 재개 (REQ-014)
    final resumeFromChunk = await _getResumeChunk(uploadId);

    for (var i = resumeFromChunk; i < totalChunks; i++) {
      // 취소 확인 (업로드 ID별)
      final cancelled = await _isUploadCancelled(uploadId);
      if (cancelled) {
        throw Exception('업로드가 취소되었습니다');
      }

      final start = i * chunkSize;
      final end = (start + chunkSize).clamp(0, fileSize);
      final chunkData = await _readChunk(file, start, end);

      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(
          chunkData,
          filename: '$fileName.part$i',
        ),
        'chunk_index': i.toString(),
        'total_chunks': totalChunks.toString(),
        'upload_id': uploadId,
        'original_filename': fileName,
        if (vocabularyId != null) 'vocabulary_id': vocabularyId,
      });

      await _dio.post(
        '${AppConfig.apiBaseUrl}/api/v1/transcriptions/chunk',
        data: formData,
        options: Options(contentType: 'multipart/form-data'),
      );

      // 완료된 청크 기록 (재개용)
      await _markChunkCompleted(uploadId, i);

      // 진행률 콜백
      onProgress?.call(ChunkUploadProgress(
        totalChunks: totalChunks,
        completedChunks: i + 1,
        currentChunk: i,
        progress: (i + 1) / totalChunks,
      ));
    }

    // 모든 청크 업로드 완료 — 병합 요청
    final mergeResponse = await _dio.post(
      '${AppConfig.apiBaseUrl}/api/v1/transcriptions/merge',
      data: {
        'upload_id': uploadId,
        'original_filename': fileName,
        'total_chunks': totalChunks,
        if (vocabularyId != null) 'vocabulary_id': vocabularyId,
      },
    );

    // 업로드 완료 후 청크 상태 정리
    await _clearUploadState(uploadId);

    return mergeResponse.data as Map<String, dynamic>;
  }

  /// 파일의 특정 구간 읽기
  Future<Uint8List> _readChunk(File file, int start, int end) async {
    final raf = await file.open();
    try {
      await raf.setPosition(start);
      final length = end - start;
      final bytes = await raf.read(length);
      return bytes;
    } finally {
      await raf.close();
    }
  }

  /// 완료된 청크 인덱스 저장 (재개용, REQ-014)
  Future<void> _markChunkCompleted(String uploadId, int chunkIndex) async {
    final prefs = await SharedPreferences.getInstance();
    final key = 'upload_chunk_$uploadId';
    final completed = prefs.getStringList(key) ?? [];
    completed.add(chunkIndex.toString());
    await prefs.setStringList(key, completed);
  }

  /// 마지막 성공 청크 이후부터 재개 (REQ-014)
  Future<int> _getResumeChunk(String uploadId) async {
    final prefs = await SharedPreferences.getInstance();
    final key = 'upload_chunk_$uploadId';
    final completed = prefs.getStringList(key) ?? [];
    if (completed.isEmpty) return 0;
    // 마지막 완료 청크의 다음부터 시작
    return completed.map(int.parse).reduce((a, b) => a > b ? a : b) + 1;
  }

  /// 업로드 취소 상태 확인
  Future<bool> _isUploadCancelled(String uploadId) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('upload_cancelled_$uploadId') ?? false;
  }

  /// 업로드 상태 정리
  Future<void> _clearUploadState(String uploadId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('upload_chunk_$uploadId');
    await prefs.remove('upload_cancelled_$uploadId');
  }

  /// 업로드 취소
  Future<void> cancelUpload(String uploadId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('upload_cancelled_$uploadId', true);
  }
}
