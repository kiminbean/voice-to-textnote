// 처리 중 화면 - SSE 실시간 상태 + 에러 UI + 펄스 애니메이션
// @MX:NOTE: SPEC-TMPL-001에서 수정 - 요약 시작 전 양식 선택 UI 추가 (REQ-TMPL-006)
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/models/template.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/providers/pipeline_provider.dart';
import 'package:voice_to_textnote/providers/template_provider.dart';
import 'package:voice_to_textnote/services/sse_service.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'package:voice_to_textnote/widgets/pipeline_progress.dart';
import 'package:voice_to_textnote/widgets/error_dialog.dart';

class ProcessingScreen extends ConsumerStatefulWidget {
  final String meetingId;

  const ProcessingScreen({super.key, required this.meetingId});

  @override
  ConsumerState<ProcessingScreen> createState() => _ProcessingScreenState();
}

class _ProcessingScreenState extends ConsumerState<ProcessingScreen>
    with SingleTickerProviderStateMixin {
  // SSE 서비스 인스턴스
  late final SseService _sseService;

  // SSE 스트림 구독
  StreamSubscription<Map<String, dynamic>>? _sseSubscription;

  // 펄스 애니메이션 컨트롤러
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();

    // 펄스 애니메이션 초기화
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 0.9, end: 1.1).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    // SSE 서비스 초기화
    _sseService = SseService(baseUrl: AppConfig.apiBaseUrl);

    // 파이프라인 시작 (Meeting의 audioFilePath 사용)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _startPipelineForMeeting();
    });
  }

  // Meeting의 audioFilePath를 가져와 파이프라인 시작
  void _startPipelineForMeeting() {
    // AsyncNotifier이므로 .value로 현재 목록 조회
    final meetings = ref.read(meetingListProvider).value ?? [];
    final meeting = meetings.where((m) => m.id == widget.meetingId).firstOrNull;

    if (meeting == null || meeting.audioFilePath == null) {
      // 미팅이 없거나 파일 경로가 없으면 홈으로 이동
      if (mounted) context.go('/');
      return;
    }

    // 이전 completed 상태가 즉시 결과 화면으로 이동하는 버그 방지
    // 새 녹음 시작 전 반드시 상태를 초기화
    ref.read(pipelineProvider.notifier).reset();

    // SSE 연결 감시 시작 (currentTaskId 변경 시 자동 연결)
    _watchTaskIdAndConnectSse();

    // 양식 선택 다이얼로그 표시 후 파이프라인 시작
    // 선택된 templateId는 요약 생성 시 사용
    _showTemplateSelectorAndStart(meeting.audioFilePath!, meeting.vocabularyId);
  }

  Future<void> _showTemplateSelectorAndStart(
    String audioFilePath,
    String? vocabularyId,
  ) async {
    if (!mounted) return;

    String? selectedTemplateId = ref.read(selectedTemplateIdProvider);

    // 바텀시트로 양식 선택 UI 표시
    final chosen = await showModalBottomSheet<String?>(
      context: context,
      isScrollControlled: true,
      isDismissible: false,
      enableDrag: false,
      builder: (ctx) => _TemplateSelectorSheet(
        initialTemplateId: selectedTemplateId,
      ),
    );

    // 바텀시트가 닫히지 않고 취소된 경우 (null 반환 = 취소)
    // 선택한 경우엔 String 또는 '' (기본 양식)
    if (chosen == null) {
      // 취소 - 홈으로 이동
      if (mounted) context.go('/');
      return;
    }

    // 선택된 양식 ID 저장 (빈 문자열 = 기본 양식, null과 동일하게 처리)
    final templateId = chosen.isEmpty ? null : chosen;
    ref.read(selectedTemplateIdProvider.notifier).state = templateId;

    // 파이프라인 시작 (업로드 → STT → DIA → MIN → SUM)
    // templateId는 SUM 단계에서 summaryApi.create() 호출 시 사용
    ref.read(pipelineProvider.notifier).startPipeline(audioFilePath,
        templateId: templateId, vocabularyId: vocabularyId);
  }

  // currentTaskId 변경 감지 시 SSE 재연결
  void _watchTaskIdAndConnectSse() {
    ref.listen<PipelineState>(pipelineProvider, (previous, next) {
      final prevTaskId = previous?.currentTaskId;
      final nextTaskId = next.currentTaskId;
      if (nextTaskId != null && nextTaskId != prevTaskId) {
        _sseSubscription?.cancel();
        _connectSse();
      }
    });
  }

  // 파이프라인 완료 시 Meeting 업데이트 및 결과 화면 이동
  void _onPipelineCompleted(PipelineState pipelineState) {
    // Meeting에 task ID들 저장 후 completed 상태로 변경
    // AsyncNotifier이므로 .value?.firstWhere 사용
    final currentMeetings = ref.read(meetingListProvider).value ?? [];
    ref.read(meetingListProvider.notifier).updateMeeting(
          widget.meetingId,
          currentMeetings.firstWhere((m) => m.id == widget.meetingId).copyWith(
                status: MeetingStatus.completed,
                minutesTaskId: pipelineState.minutesTaskId,
                summaryTaskId: pipelineState.summaryTaskId,
              ),
        );

    if (mounted) {
      context.go('/result/${widget.meetingId}');
    }
  }

  // SSE 연결 시도 - 실패 시 폴링 폴백
  void _connectSse() {
    final currentTaskId = ref.read(pipelineProvider).currentTaskId;
    if (currentTaskId == null) return;

    _sseSubscription = _sseService.connect(currentTaskId).listen(
      (event) => _handleSseEvent(event),
      onError: (_) {
        // SSE 실패 - 기존 폴링 방식으로 폴백 (PipelineProvider가 처리)
      },
    );
  }

  // SSE 이벤트 처리
  void _handleSseEvent(Map<String, dynamic> event) {
    final status = event['status'] as String?;

    if (status == 'completed') {
      // 완료 이벤트 - 결과 화면으로 이동
      if (mounted) {
        context.go('/result/${widget.meetingId}');
      }
    } else if (status == 'failed') {
      // 실패 이벤트 - 에러 다이얼로그 표시
      if (mounted) {
        _showErrorDialog(event['error'] as String? ?? '처리 중 오류가 발생했습니다');
      }
    }
  }

  // 오류 다이얼로그 표시
  void _showErrorDialog(String message) {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ErrorDialog(
        message: message,
        onRetry: () {
          // 파이프라인 재시작
          ref.read(pipelineProvider.notifier).reset();
          context.go('/');
        },
        onGoHome: () => context.go('/'),
      ),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _sseSubscription?.cancel();
    _sseService.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pipelineState = ref.watch(pipelineProvider);

    // 완료/실패 상태 시 자동 처리
    ref.listen<PipelineState>(pipelineProvider, (previous, next) {
      if (next.currentStep == PipelineStep.completed && mounted) {
        _onPipelineCompleted(next);
      } else if (next.currentStep == PipelineStep.failed &&
          next.errorMessage != null &&
          mounted) {
        // Meeting 상태를 failed로 업데이트 (AsyncNotifier이므로 .value 사용)
        final meetings = ref.read(meetingListProvider).value ?? [];
        final meeting =
            meetings.where((m) => m.id == widget.meetingId).firstOrNull;
        if (meeting != null) {
          ref.read(meetingListProvider.notifier).updateMeeting(
                widget.meetingId,
                meeting.copyWith(status: MeetingStatus.failed),
              );
        }
        _showErrorDialog(next.errorMessage!);
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('처리 중'),
        automaticallyImplyLeading: false, // 뒤로가기 비활성화
        actions: [
          TextButton(
            onPressed: () async {
              await ref.read(pipelineProvider.notifier).cancelPipeline();
              if (context.mounted) context.go('/');
            },
            child: const Text('취소'),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 펄스 애니메이션 인디케이터
            AnimatedBuilder(
              animation: _pulseAnimation,
              builder: (context, child) => Transform.scale(
                scale: _pulseAnimation.value,
                child: child,
              ),
              child: Icon(
                Icons.settings_voice,
                size: 64,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
            const SizedBox(height: 24),
            // 처리 상태 텍스트
            Text(
              _getStepText(pipelineState.currentStep),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 32),
            // 파이프라인 진행 표시
            PipelineProgress(pipelineState: pipelineState),
            const SizedBox(height: 24),
            // 진행률 퍼센트 표시
            Text(
              '${(pipelineState.progress * 100).toInt()}%',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            // 오류 메시지 표시
            if (pipelineState.errorMessage != null) ...[
              const SizedBox(height: 16),
              Text(
                '오류: ${pipelineState.errorMessage}',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.red),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // 처리 단계에 따른 텍스트 반환
  String _getStepText(PipelineStep step) {
    return switch (step) {
      PipelineStep.idle => '처리 시작 대기 중',
      PipelineStep.uploading => '오디오 파일 업로드 중...',
      PipelineStep.transcribing => '음성 인식(STT) 처리 중...',
      PipelineStep.diarizing => '화자 분리 처리 중...',
      PipelineStep.generatingMinutes => '회의록 생성 중...',
      PipelineStep.summarizing => 'AI 요약 생성 중...',
      PipelineStep.completed => '처리 완료!',
      PipelineStep.failed => '처리 실패',
    };
  }
}

// 양식 선택 바텀시트 위젯 - SPEC-TMPL-001 REQ-TMPL-006
class _TemplateSelectorSheet extends ConsumerWidget {
  // 현재 선택된 양식 ID (null = 기본 양식)
  final String? initialTemplateId;

  const _TemplateSelectorSheet({this.initialTemplateId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final templatesAsync = ref.watch(templateListProvider);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 헤더
            Row(
              children: [
                const Icon(Icons.folder_special_outlined),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    '요약 양식 선택',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(null),
                ),
              ],
            ),
            const Divider(),

            // 기본 양식 옵션 (항상 첫 번째)
            ListTile(
              leading: const Icon(Icons.article_outlined),
              title: const Text('기본 양식'),
              subtitle: const Text('AI가 자동으로 구성한 양식'),
              trailing: initialTemplateId == null
                  ? const Icon(Icons.check_circle, color: Colors.blue)
                  : null,
              onTap: () => Navigator.of(context).pop(''),
            ),

            // 업로드된 양식 목록
            templatesAsync.when(
              loading: () => const Padding(
                padding: EdgeInsets.all(16),
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (_, __) => const Padding(
                padding: EdgeInsets.all(8),
                child: Text(
                  '양식 목록을 불러올 수 없습니다',
                  style: TextStyle(color: Colors.grey),
                  textAlign: TextAlign.center,
                ),
              ),
              data: (templates) => templates.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.all(8),
                      child: Text(
                        '등록된 양식이 없습니다',
                        style: TextStyle(color: Colors.grey),
                        textAlign: TextAlign.center,
                      ),
                    )
                  : Column(
                      children: templates
                          .map(
                            (template) => _TemplateOption(
                              template: template,
                              isSelected:
                                  initialTemplateId == template.templateId,
                              onTap: () => Navigator.of(context)
                                  .pop(template.templateId),
                            ),
                          )
                          .toList(),
                    ),
            ),

            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

// 양식 선택 옵션 위젯
class _TemplateOption extends StatelessWidget {
  final Template template;
  final bool isSelected;
  final VoidCallback onTap;

  const _TemplateOption({
    required this.template,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final isPdf = template.format.toLowerCase() == 'pdf';
    final formatIcon = isPdf ? Icons.picture_as_pdf : Icons.description;
    final formatColor = isPdf ? Colors.red : Colors.blue;

    return ListTile(
      leading: Icon(formatIcon, color: formatColor),
      title: Text(
        template.name,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        template.format.toUpperCase(),
        style: const TextStyle(fontSize: 12),
      ),
      trailing: isSelected
          ? const Icon(Icons.check_circle, color: Colors.blue)
          : null,
      onTap: onTap,
    );
  }
}
