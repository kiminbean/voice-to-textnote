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

// task_id 기반 결과 로딩 프로바이더 (family로 파라미터화)
// @MX:ANCHOR: ResultScreen에서 meetingId로 결과 데이터 로드
// @MX:REASON: ProcessingScreen → ResultScreen 라우팅 시 동일 taskId 사용
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
