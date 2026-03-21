// 결과 데이터 로딩 상태 프로바이더
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';

// 결과 데이터 모델
class MeetingResult {
  // 회의록 텍스트
  final String minutes;

  // AI 요약 텍스트
  final String summary;

  // 액션 아이템 목록
  final List<String> actionItems;

  const MeetingResult({
    required this.minutes,
    required this.summary,
    required this.actionItems,
  });
}

// 회의록 결과 로딩 프로바이더 (minutesTaskId 기반)
// @MX:ANCHOR: ResultScreen _TranscriptTab에서 minutesTaskId로 회의록 로드
// @MX:REASON: 파이프라인의 minTaskId를 통해 회의록 결과 조회
final minutesResultProvider =
    FutureProvider.family<String, String>((ref, minutesTaskId) async {
  final minApi = ref.watch(minutesApiProvider);
  final data = await minApi.getResult(minutesTaskId);
  return data['minutes'] as String? ?? '';
});

// 요약 결과 로딩 프로바이더 (summaryTaskId 기반)
// @MX:ANCHOR: ResultScreen _SummaryTab, _ActionItemsTab에서 summaryTaskId로 요약 로드
// @MX:REASON: 파이프라인의 sumTaskId를 통해 요약 결과 조회
final summaryResultProvider =
    FutureProvider.family<Map<String, dynamic>, String>((ref, summaryTaskId) async {
  final sumApi = ref.watch(summaryApiProvider);
  return sumApi.getResult(summaryTaskId);
});

// 기존 통합 프로바이더 (하위 호환성 유지 - 두 ID가 동일한 경우)
// task_id 기반 결과 로딩 프로바이더 (family로 파라미터화)
final resultProvider =
    FutureProvider.family<MeetingResult, String>((ref, taskId) async {
  final minApi = ref.watch(minutesApiProvider);
  final sumApi = ref.watch(summaryApiProvider);

  // 병렬로 두 API 동시 요청
  final results = await Future.wait([
    minApi.getResult(taskId),
    sumApi.getResult(taskId),
  ]);

  final minutesData = results[0];
  final summaryData = results[1];

  return MeetingResult(
    minutes: minutesData['minutes'] as String? ?? '',
    summary: summaryData['summary'] as String? ?? '',
    actionItems: (summaryData['action_items'] as List<dynamic>? ?? [])
        .cast<String>(),
  );
});
