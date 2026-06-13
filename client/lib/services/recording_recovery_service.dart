// SPEC-MOBILE-004 T-009: 녹음 복원 서비스
// REQ-MOBILE-004-002-01: 녹음 시작 시 파일 경로를 SharedPreferences에 저장
// REQ-MOBILE-004-002-02: 앱 재시작 시 미완료 녹음 감지

import 'package:shared_preferences/shared_preferences.dart';

class RecordingRecoveryService {
  static const _pathKey = 'active_recording_path';
  static const _startedAtKey = 'active_recording_started_at';

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

  Future<void> clearActiveRecording() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_pathKey);
    await prefs.remove(_startedAtKey);
  }
}
