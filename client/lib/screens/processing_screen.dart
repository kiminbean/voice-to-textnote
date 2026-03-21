// 처리 중 화면 - SSE 실시간 상태 + 에러 UI + 펄스 애니메이션
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/pipeline_state.dart';
import 'package:voice_to_textnote/providers/pipeline_provider.dart';
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

    // 실시간 이벤트 구독 시작
    _connectSse();
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

    // 완료 상태 시 자동 이동
    ref.listen<PipelineState>(pipelineProvider, (previous, next) {
      if (next.currentStep == PipelineStep.completed && mounted) {
        context.go('/result/${widget.meetingId}');
      } else if (next.currentStep == PipelineStep.failed &&
          next.errorMessage != null &&
          mounted) {
        _showErrorDialog(next.errorMessage!);
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('처리 중'),
        automaticallyImplyLeading: false, // 뒤로가기 비활성화
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
