// 녹음 화면
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/providers/recording_provider.dart';

class RecordingScreen extends ConsumerStatefulWidget {
  const RecordingScreen({super.key});

  @override
  ConsumerState<RecordingScreen> createState() => _RecordingScreenState();
}

class _RecordingScreenState extends ConsumerState<RecordingScreen> {
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
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

  // 녹음 토글
  void _toggleRecording() {
    final status = ref.read(recordingProvider).status;

    if (status == RecordingStatus.idle || status == RecordingStatus.stopped) {
      ref.read(recordingProvider.notifier).startRecording();
      _startTimer();
    } else if (status == RecordingStatus.recording) {
      ref.read(recordingProvider.notifier).stopRecording();
      _stopTimer();
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
            // 녹음 버튼
            GestureDetector(
              onTap: _toggleRecording,
              child: Container(
                width: 100,
                height: 100,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isRecording ? Colors.red : Colors.blue,
                ),
                child: Icon(
                  isRecording ? Icons.stop : Icons.mic,
                  color: Colors.white,
                  size: 48,
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
