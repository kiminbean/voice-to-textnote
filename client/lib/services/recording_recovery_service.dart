// SPEC-MOBILE-004 T-009: 녹음 복원 서비스
// SPEC-MOBILE-005: 파일 무결성 검사 추가 (REQ-005, REQ-006)
// REQ-MOBILE-004-002-01: 녹음 시작 시 파일 경로를 SharedPreferences에 저장
// REQ-MOBILE-004-002-02: 앱 재시작 시 미완료 녹음 감지
// REQ-005-02: 복구 시 파일 무결성 검사 (빈 파일/손상 파일 감지)

import 'dart:io';
import 'package:shared_preferences/shared_preferences.dart';

class RecordingRecoveryService {
  static const _pathKey = 'active_recording_path';
  static const _startedAtKey = 'active_recording_started_at';

  /// 최소 유효 파일 크기 (바이트) — 이보다 작으면 손상된 파일로 간주
  static const _minValidFileSize = 1024; // 1KB

  Future<void> saveActiveRecording(
    String filePath, {
    required String startedAt,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_pathKey, filePath);
    await prefs.setString(_startedAtKey, startedAt);
  }

  Future<String?> getActiveRecordingPath() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_pathKey);
  }

  Future<String?> getActiveRecordingStartedAt() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_startedAtKey);
  }

  Future<bool> hasActiveRecording() async {
    final prefs = await SharedPreferences.getInstance();
    final path = prefs.getString(_pathKey);
    return path != null && path.isNotEmpty;
  }

  /// SPEC-MOBILE-005 REQ-005-02: 복구 시 파일 무결성 검사
  /// 파일이 존재하고 최소 크기 이상인지 확인
  /// @returns true: 복구 가능한 유효한 파일, false: 손상/누락된 파일
  Future<bool> isRecoverable() async {
    final path = await getActiveRecordingPath();
    if (path == null || path.isEmpty) return false;

    final file = File(path);
    if (!await file.exists()) return false;

    final fileSize = await file.length();
    return fileSize >= _minValidFileSize;
  }

  /// SPEC-MOBILE-005 REQ-005-02: 무결성 검사 포함된 복구 경로 반환
  /// 파일이 유효하면 경로를, 손상되었으면 null을 반환하고 기록을 정리
  Future<String?> getValidRecoveryPath() async {
    final recoverable = await isRecoverable();
    if (!recoverable) {
      // 손상된 파일 기록 정리
      await clearActiveRecording();
      return null;
    }
    return await getActiveRecordingPath();
  }

  Future<void> clearActiveRecording() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_pathKey);
    await prefs.remove(_startedAtKey);
  }
}
