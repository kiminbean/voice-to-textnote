// 녹음 화면
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/providers/recording_provider.dart';

class RecordingScreen extends ConsumerStatefulWidget {
  const RecordingScreen({super.key});

  @override
  ConsumerState<RecordingScreen> createState() => _RecordingScreenState();
}

class _RecordingScreenState extends ConsumerState<RecordingScreen>
    with SingleTickerProviderStateMixin {
  Timer? _timer;
  late AnimationController _scaleController;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _scaleController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 150),
      lowerBound: 0.9,
      upperBound: 1.0,
      value: 1.0,
    );
    _scaleAnimation = CurvedAnimation(
      parent: _scaleController,
      curve: Curves.easeInOut,
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    _scaleController.dispose();
    super.dispose();
  }

  // 타이머 시작
  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      final current = ref.read(recordingProvider).elapsedSeconds;
      ref.read(recordingProvider.notifier).updateElapsedSeconds(current + 1);
    });
  }

  // 타이머 중지
  void _stopTimer() {
    _timer?.cancel();
    _timer = null;
  }

  // 녹음 토글 - 실제 마이크 녹음 시작/중지 처리
  Future<void> _toggleRecording() async {
    final status = ref.read(recordingProvider).status;

    if (status == RecordingStatus.idle || status == RecordingStatus.stopped) {
      // 실제 녹음 시작 (마이크 권한 요청 포함)
      await ref.read(recordingProvider.notifier).startRecording();

      // 권한이 거부되어 상태가 idle인 경우 타이머 시작 안함
      if (ref.read(recordingProvider).status == RecordingStatus.recording) {
        _startTimer();
      }
    } else if (status == RecordingStatus.recording) {
      _stopTimer();

      // 실제 녹음 중지 및 파일 저장
      await ref.read(recordingProvider.notifier).stopRecording();

      // 녹음 완료 후 Meeting 생성 및 목록에 추가
      await _createMeetingAndNavigate();
    }
  }

  // Meeting 객체 생성 후 목록에 추가, 처리 화면으로 이동
  Future<void> _createMeetingAndNavigate() async {
    final recordingState = ref.read(recordingProvider);
    final elapsedSeconds = recordingState.elapsedSeconds;
    final filePath = recordingState.filePath;

    // 오디오 파일이 없으면 처리 불가
    if (filePath == null) return;

    // 고유 ID 생성 (타임스탬프 기반)
    final meetingId = 'meeting_${DateTime.now().millisecondsSinceEpoch}';

    // 녹음 일시 기반 제목 생성 (예: "미팅 2025-01-15 14:30")
    final now = DateTime.now();
    final title =
        '미팅 ${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')} '
        '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';

    // processing 상태로 Meeting 생성 (파이프라인이 완료되면 completed로 변경됨)
    final newMeeting = Meeting(
      id: meetingId,
      title: title,
      createdAt: now,
      status: MeetingStatus.processing,
      duration: Duration(seconds: elapsedSeconds),
      audioFilePath: filePath,
    );

    // meetingListProvider에 추가
    ref.read(meetingListProvider.notifier).addMeeting(newMeeting);

    // recordingProvider 초기화
    ref.read(recordingProvider.notifier).reset();

    // 처리 화면으로 이동 (파이프라인 진행 상태 표시)
    if (mounted) {
      context.go('/processing/$meetingId');
    }
  }

  // 경과 시간을 MM:SS 형식으로 변환
  String _formatTime(int seconds) {
    final minutes = seconds ~/ 60;
    final secs = seconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(recordingProvider);
    final isRecording = state.status == RecordingStatus.recording;

    return Scaffold(
      appBar: AppBar(
        title: const Text('새 녹음'),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // 타이머 표시
            Text(
              _formatTime(state.elapsedSeconds),
              style: Theme.of(context).textTheme.displayLarge?.copyWith(
                    fontFamily: 'monospace',
                    fontFeatures: const [],
                  ),
            ),
            const SizedBox(height: 32),
            // 녹음 상태 텍스트
            Text(
              _getStatusText(state.status),
              style: TextStyle(
                color: isRecording ? Colors.red : Colors.grey,
                fontSize: 16,
              ),
            ),
            const SizedBox(height: 48),
            // 녹음 버튼 (스케일 애니메이션 피드백)
            ScaleTransition(
              scale: _scaleAnimation,
              child: Semantics(
                button: true,
                label: isRecording ? '녹음 중지' : '녹음 시작',
                child: Material(
                  color: isRecording ? Colors.red : Theme.of(context).colorScheme.primary,
                  shape: const CircleBorder(),
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                    onTap: _toggleRecording,
                    onTapDown: (_) => _scaleController.reverse(),
                    onTapUp: (_) => _scaleController.forward(),
                    onTapCancel: () => _scaleController.forward(),
                    splashColor: Colors.white.withAlpha(80),
                    child: SizedBox(
                      width: 100,
                      height: 100,
                      child: Icon(
                        isRecording ? Icons.stop : Icons.mic,
                        color: Colors.white,
                        size: 48,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 상태에 따른 텍스트 반환
  String _getStatusText(RecordingStatus status) {
    return switch (status) {
      RecordingStatus.idle => '탭하여 녹음 시작',
      RecordingStatus.recording => '녹음 중...',
      RecordingStatus.paused => '일시 정지됨',
      RecordingStatus.stopped => '녹음 완료',
    };
  }
}
