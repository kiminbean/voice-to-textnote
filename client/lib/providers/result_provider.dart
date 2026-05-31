// 결과 데이터 로딩 상태 프로바이더
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/action_item.dart';
import 'package:voice_to_textnote/models/mind_map_result.dart';
import 'package:voice_to_textnote/models/summary_result.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';

// 결과 데이터 모델 (keyDecisions, nextSteps 포함 - SPEC-APP-004 REQ-APP-041)
class MeetingResult {
  // 회의록 텍스트
  final String minutes;

  // AI 요약 텍스트
  final String summary;

  // 구조화된 액션 아이템 목록 (SPEC-APP-003 REQ-APP-031)
  final List<ActionItem> actionItems;

  // 주요 결정 사항 목록 (SPEC-APP-004 REQ-APP-042)
  final List<String> keyDecisions;

  // 다음 단계 목록 (SPEC-APP-004 REQ-APP-043)
  final List<String> nextSteps;

  const MeetingResult({
    required this.minutes,
    required this.summary,
    required this.actionItems,
    this.keyDecisions = const [],
    this.nextSteps = const [],
  });
}

// 회의록 결과 로딩 프로바이더 (minutesTaskId 기반)
// @MX:ANCHOR: ResultScreen _TranscriptTab에서 minutesTaskId로 회의록 로드
// @MX:REASON: 파이프라인의 minTaskId를 통해 회의록 결과 조회
final minutesResultProvider =
    FutureProvider.family<String, String>((ref, minutesTaskId) async {
  final minApi = ref.watch(minutesApiProvider);
  final data = await minApi.getResult(minutesTaskId);

  // markdown이 있으면 우선 사용
  final markdown = data['markdown'] as String?;
  if (markdown != null && markdown.isNotEmpty) return markdown;

  // segments에서 회의록 텍스트 조합
  final segments = data['segments'] as List<dynamic>? ?? [];
  if (segments.isEmpty) return '';

  final buffer = StringBuffer();
  for (final seg in segments) {
    final speaker = seg['speaker_name'] ?? '알 수 없음';
    final text = seg['text'] ?? '';
    buffer.writeln('[$speaker] $text');
  }
  return buffer.toString().trim();
});

// 요약 결과 로딩 프로바이더 (summaryTaskId 기반) - SPEC-APP-004 REQ-APP-041
// @MX:ANCHOR: ResultScreen _SummaryTab, _ActionItemsTab에서 summaryTaskId로 요약 로드
// @MX:REASON: SummaryResult 타입 안전성 보장, key_decisions/next_steps 포함
final summaryResultProvider =
    FutureProvider.family<SummaryResult, String>((ref, summaryTaskId) async {
  final sumApi = ref.watch(summaryApiProvider);
  final data = await sumApi.getResult(summaryTaskId);
  return SummaryResult.fromJson(data);
});

// 관계 추론형 마인드맵 결과 로딩 프로바이더.
// 백엔드가 비동기 생성 작업을 반환하므로 create → status polling → result 순서로 처리한다.
final mindMapResultProvider =
    FutureProvider.family<MindMapResult, String>((ref, summaryTaskId) async {
  final sumApi = ref.watch(summaryApiProvider);
  final createData = await sumApi.createMindMap(summaryTaskId);
  final mindMapTaskId = createData['task_id'] as String? ?? '';

  if (mindMapTaskId.isEmpty) {
    throw StateError('마인드맵 작업 ID를 받지 못했습니다.');
  }

  for (var attempt = 0; attempt < 30; attempt++) {
    final statusData = await sumApi.getMindMapStatus(mindMapTaskId);
    final status = statusData['status'] as String? ?? 'pending';

    if (status == 'completed') {
      final resultData = await sumApi.getMindMapResult(mindMapTaskId);
      return MindMapResult.fromJson(resultData);
    }

    if (status == 'failed') {
      final message =
          statusData['error_message'] as String? ?? '마인드맵 생성에 실패했습니다.';
      throw StateError(message);
    }

    await Future<void>.delayed(const Duration(seconds: 1));
  }

  throw StateError('마인드맵 생성 시간이 초과되었습니다.');
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

  // SummaryResult를 통해 타입 안전하게 파싱
  final summaryResult = SummaryResult.fromJson(summaryData);

  return MeetingResult(
    minutes: minutesData['minutes'] as String? ?? '',
    summary: summaryResult.summaryText,
    actionItems: summaryResult.actionItems,
    keyDecisions: summaryResult.keyDecisions,
    nextSteps: summaryResult.nextSteps,
  );
});
