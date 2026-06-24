// 결과 데이터 로딩 상태 프로바이더
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:voice_to_textnote/models/action_item.dart';
import 'package:voice_to_textnote/models/mind_map_result.dart';
import 'package:voice_to_textnote/models/summary_result.dart';
import 'package:voice_to_textnote/providers/speaker_provider.dart';
import 'package:voice_to_textnote/services/minutes_api.dart';
import 'package:voice_to_textnote/services/statistics_api.dart';
import 'package:voice_to_textnote/services/bookmark_api.dart';
import 'package:voice_to_textnote/services/sentiment_api.dart';
import 'package:voice_to_textnote/services/summary_api.dart';
import 'package:voice_to_textnote/services/tone_api.dart';
import 'package:voice_to_textnote/models/tone_model.dart';

class TranscriptSegment {
  final String? speakerId;
  final String speakerName;
  final String text;
  final double start;
  final double end;
  final int speakerIndex;
  final bool isEstimatedSpeaker;
  final double? voiceprintSimilarity;

  const TranscriptSegment({
    this.speakerId,
    required this.speakerName,
    required this.text,
    required this.start,
    required this.end,
    this.speakerIndex = 0,
    this.isEstimatedSpeaker = false,
    this.voiceprintSimilarity,
  });

  factory TranscriptSegment.fromJson(Map<String, dynamic> json, int index) =>
      TranscriptSegment(
        speakerId: json['speaker_id'] as String?,
        speakerName: json['identified_speaker_name'] as String? ??
            json['speaker_name'] as String? ??
            '알 수 없음',
        text: json['text'] as String? ?? '',
        start: (json['start'] as num?)?.toDouble() ?? 0.0,
        end: (json['end'] as num?)?.toDouble() ?? 0.0,
        speakerIndex: index,
        isEstimatedSpeaker: json['identified_speaker_name'] != null,
        voiceprintSimilarity:
            (json['voiceprint_similarity'] as num?)?.toDouble(),
      );
}

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
  final data = await ref.watch(minutesRawResultProvider(minutesTaskId).future);
  final speakerNames =
      await ref.watch(speakerNameMapProvider(minutesTaskId).future);

  // markdown이 있으면 우선 사용
  final markdown = data['markdown'] as String?;

  // segments에서 회의록 텍스트 조합
  final segments = data['segments'] as List<dynamic>? ?? [];
  if (markdown != null && markdown.isNotEmpty && speakerNames.isEmpty) {
    return markdown;
  }
  if (segments.isEmpty) return '';

  final buffer = StringBuffer();
  for (final seg in segments) {
    final segment = seg as Map<String, dynamic>;
    final speakerId = segment['speaker_id'] as String?;
    final identifiedName = segment['identified_speaker_name'] as String?;
    final speaker = identifiedName ??
        (speakerId != null
            ? speakerNames[speakerId] ?? segment['speaker_name'] ?? '알 수 없음'
            : segment['speaker_name'] ?? '알 수 없음');
    final text = segment['text'] ?? '';
    buffer.writeln('[$speaker] $text');
  }
  return buffer.toString().trim();
});

final transcriptSegmentsProvider =
    FutureProvider.family<List<TranscriptSegment>, String>(
        (ref, minutesTaskId) async {
  final data = await ref.watch(minutesRawResultProvider(minutesTaskId).future);
  final speakerNames =
      await ref.watch(speakerNameMapProvider(minutesTaskId).future);
  final raw = data['segments'] as List<dynamic>? ?? [];
  final seen = <String, int>{};
  return raw.asMap().entries.map((e) {
    final seg = TranscriptSegment.fromJson(
      e.value as Map<String, dynamic>,
      e.key,
    );
    final displayName = seg.isEstimatedSpeaker
        ? seg.speakerName
        : seg.speakerId != null
            ? speakerNames[seg.speakerId!] ?? seg.speakerName
            : seg.speakerName;
    final key = seg.speakerId ?? displayName;
    seen.putIfAbsent(key, () => seen.length);
    return TranscriptSegment(
      speakerId: seg.speakerId,
      speakerName: displayName,
      text: seg.text,
      start: seg.start,
      end: seg.end,
      speakerIndex: seen[key]!,
      isEstimatedSpeaker: seg.isEstimatedSpeaker,
      voiceprintSimilarity: seg.voiceprintSimilarity,
    );
  }).toList();
});

final minutesRawResultProvider =
    FutureProvider.family<Map<String, dynamic>, String>((ref, minutesTaskId) {
  final minApi = ref.watch(minutesApiProvider);
  return minApi.getResult(minutesTaskId);
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
    Map<String, dynamic> statusData;
    try {
      statusData = await sumApi.getMindMapStatus(mindMapTaskId);
    } on DioException catch (error) {
      if (error.response?.statusCode == 404 && attempt < 5) {
        await Future<void>.delayed(const Duration(seconds: 1));
        continue;
      }
      rethrow;
    }
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

final statisticsProvider =
    FutureProvider.family<StatisticsResponse, String>((ref, taskId) async {
  final api = ref.watch(statisticsApiProvider);
  return api.getStatistics(taskId);
});

final bookmarksProvider =
    FutureProvider.family<List<Bookmark>, String>((ref, taskId) async {
  final api = ref.watch(bookmarkApiProvider);
  return api.list(taskId: taskId);
});

final sentimentProvider =
    FutureProvider.family<List<SentimentSegment>, String>((ref, taskId) async {
  final api = ref.watch(sentimentApiProvider);
  try {
    return api.getByMeeting(taskId);
  } catch (_) {
    return <SentimentSegment>[];
  }
});

// SPEC-SENTIMENT-001: 감정 분석 전체 응답 프로바이더 (REQ-SEN-008/009/010)
// @MX:ANCHOR: _SentimentTab에서 minutesTaskId로 감정 분석 결과 로드
// @MX:REASON: 백엔드 비동기 감정 분석(openAI) 작업을 create→poll→fetch 순서로 처리
// mindMapResultProvider와 동일한 패턴 - POST /sentiment 생성 후 폴링, GET /sentiment/{taskId}로 결과 조회
// 오류를 삼키지 않고 AsyncValue.error로 전파하여 ErrorRetryWidget이 표시되도록 함
final sentimentFullProvider =
    FutureProvider.family<SentimentFullResponse, String>(
        (ref, minutesTaskId) async {
  final api = ref.watch(sentimentApiProvider);

  // 1. 감정 분석 태스크 생성 (POST /sentiment → Celery + OpenAI gpt-4o-mini)
  final createData = await api.create(minutesTaskId);
  final sentimentTaskId = createData['task_id'] as String? ?? '';

  if (sentimentTaskId.isEmpty) {
    throw StateError('감정 분석 작업 ID를 받지 못했습니다.');
  }

  // 2. 완료 대기 - 폴링 (최대 5분 = 150회 × 2초)
  // OpenAI gpt-4o-mini 감정 분석은 회의록 길이에 따라 3~30초 소요
  for (var attempt = 0; attempt < 150; attempt++) {
    final statusData = await api.getStatus(sentimentTaskId);
    final status = statusData['status'] as String? ?? 'pending';

    if (status == 'completed') {
      // 3. 결과 조회 (GET /sentiment/{task_id} → SentimentFullResponse)
      return api.getFullResult(sentimentTaskId);
    }

    if (status == 'failed') {
      final message =
          statusData['error_message'] as String? ?? '감정 분석에 실패했습니다.';
      throw StateError(message);
    }

    await Future<void>.delayed(const Duration(seconds: 2));
  }

  throw StateError('감정 분석 생성 시간이 초과되었습니다.');
});

// SPEC-TONE-001: 톤 분석 응답 프로바이더 (REQ-TONE-012, REQ-TONE-013)
// @MX:ANCHOR: ResultScreen _SentimentContent → ToneSection에서 meetingId로 톤 분석 로드
// @MX:REASON: sentimentFullProvider와 동일한 패턴 - silent fallback 금지 (REQ-TONE-013)
// 오류를 삼키지 않고 AsyncValue.error로 전파하여 ToneSection의 ErrorRetryWidget이 표시되도록 함
final toneProvider =
    FutureProvider.family<ToneResponse, String>((ref, meetingId) async {
  final api = ref.watch(toneApiProvider);
  return api.getToneByMeeting(meetingId);
});

// 기존 통합 프로바이더 (하위 호환성 유지 - 두 ID가 동일한 경우)
// task_id 기반 결과 로딩 프로바이더 (family로 파라미터화)
final resultProvider =
    FutureProvider.family<MeetingResult, String>((ref, taskId) async {
  final sumApi = ref.watch(summaryApiProvider);

  // 병렬로 두 API 동시 요청
  final results = await Future.wait([
    ref.watch(minutesRawResultProvider(taskId).future),
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
