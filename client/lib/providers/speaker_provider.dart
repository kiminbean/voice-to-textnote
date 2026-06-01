// 화자 프로필 상태 관리 — SPEC-SPEAKER-001
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/speaker_profile.dart';
import 'package:voice_to_textnote/services/speaker_api.dart';

/// 화자 프로필 목록 (전역 + 회의별)
/// taskId를 전달하면 해당 회의 + 전역 프로필을 함께 반환
final speakerListProvider =
    FutureProvider.family<List<SpeakerProfile>, String?>((ref, taskId) async {
  final api = ref.watch(speakerApiProvider);
  return api.list(taskId: taskId);
});

/// 화자 이름 매핑: speakerLabel → displayName
/// 트랜스크립트 표시 시 SPEAKER_00 대신 표시 이름 사용
final speakerNameMapProvider =
    FutureProvider.family<Map<String, String>, String?>((ref, taskId) async {
  final profiles = await ref.watch(speakerListProvider(taskId).future);
  return {for (final p in profiles) p.speakerLabel: p.displayName};
});
