// 녹음 화면 — 모던 미니멀 (펄스 애니메이션 + 모노스페이스 타이머)
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/providers/recording_provider.dart';
import 'package:voice_to_textnote/providers/vocabulary_provider.dart';
import 'package:voice_to_textnote/providers/notification_provider.dart';
import 'package:voice_to_textnote/services/permission_service.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';
import 'package:voice_to_textnote/theme/app_typography.dart';
import 'package:voice_to_textnote/widgets/permission_dialog.dart';
import 'package:voice_to_textnote/widgets/recording_recovery_dialog.dart';

class RecordingScreen extends ConsumerStatefulWidget {
  const RecordingScreen({super.key});

  @override
  ConsumerState<RecordingScreen> createState() => _RecordingScreenState();
}

class _RecordingScreenState extends ConsumerState<RecordingScreen>
    with TickerProviderStateMixin, WidgetsBindingObserver {
  Timer? _timer;
  late AnimationController _scaleController;
  late Animation<double> _scaleAnimation;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;
  String? _selectedVocabularyId;
  bool _isPermissionChecked = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _scaleController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 150),
      lowerBound: 0.9,
      upperBound: 1.0,
      value: 1.0,
    );
    _scaleAnimation = CurvedAnimation(parent: _scaleController, curve: Curves.easeInOut);
    // 녹음 중 펄스 링
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    );
    _pulseAnimation = CurvedAnimation(parent: _pulseController, curve: Curves.easeOut);
    _checkPermissions();
    _checkInterruptedRecording();
  }

  Future<void> _checkInterruptedRecording() async {
    final interruptedPath =
        await ref.read(recordingProvider.notifier).checkInterruptedRecording();
    if (interruptedPath != null && mounted) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (context) => RecordingRecoveryDialog(
            recordingPath: interruptedPath,
            onDiscard: () {
              ref.read(recordingProvider.notifier).discardInterruptedRecording();
              Navigator.of(context).pop();
            },
            onResume: () {
              ref.read(recordingProvider.notifier).setFilePath(interruptedPath);
              Navigator.of(context).pop();
            },
          ),
        );
      });
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final recordingStatus = ref.read(recordingProvider).status;
    switch (state) {
      case AppLifecycleState.paused:
        if (recordingStatus == RecordingStatus.recording) _stopTimer();
        break;
      case AppLifecycleState.resumed:
        if (recordingStatus == RecordingStatus.recording) _startTimer();
        break;
      case AppLifecycleState.inactive:
      case AppLifecycleState.hidden:
      case AppLifecycleState.detached:
        break;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    _scaleController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _checkPermissions() async {
    final permissionService = ref.read(permissionServiceProvider);
    final micStatus = await permissionService.checkMicrophonePermission();
    if (micStatus != PermissionStatus.granted) {
      if (mounted) _showPermissionDialog(PermissionType.microphone);
    } else {
      setState(() => _isPermissionChecked = true);
    }
  }

  void _showPermissionDialog(PermissionType type) {
    showDialog(
      context: context,
      builder: (context) => PermissionDialog(
        permissionType: type,
        onRequest: () => _requestPermission(type),
        onOpenSettings: () => _openSettings(),
      ),
    );
  }

  Future<void> _requestPermission(PermissionType type) async {
    final permissionService = ref.read(permissionServiceProvider);
    if (type == PermissionType.microphone) {
      final status = await permissionService.requestMicrophonePermission();
      if (status == PermissionStatus.permanentlyDenied) {
        if (mounted) _showPermanentlyDeniedDialog(type);
      } else if (status == PermissionStatus.granted) {
        setState(() => _isPermissionChecked = true);
      }
    }
  }

  void _showPermanentlyDeniedDialog(PermissionType type) {
    showDialog(
      context: context,
      builder: (context) => PermanentlyDeniedDialog(
        permissionType: type,
        onOpenSettings: () => _openSettings(),
      ),
    );
  }

  Future<void> _openSettings() async => openAppSettings();

  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      final current = ref.read(recordingProvider).elapsedSeconds;
      ref.read(recordingProvider.notifier).updateElapsedSeconds(current + 1);
    });
  }

  void _stopTimer() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> _toggleRecording() async {
    if (!_isPermissionChecked) {
      await _checkPermissions();
      return;
    }
    final status = ref.read(recordingProvider).status;
    if (status == RecordingStatus.idle || status == RecordingStatus.stopped) {
      await HapticFeedback.mediumImpact();
      await ref.read(recordingProvider.notifier).startRecording();
      if (ref.read(recordingProvider).status == RecordingStatus.recording) {
        _startTimer();
        _pulseController.repeat();
      }
    } else if (status == RecordingStatus.recording) {
      await HapticFeedback.heavyImpact();
      _stopTimer();
      _pulseController.stop();
      await ref.read(recordingProvider.notifier).stopRecording();
      await _createMeetingAndNavigate();
    }
  }

  Future<void> _createMeetingAndNavigate() async {
    final recordingState = ref.read(recordingProvider);
    final elapsedSeconds = recordingState.elapsedSeconds;
    final filePath = recordingState.filePath;
    if (filePath == null) return;

    final meetingId = 'meeting_${DateTime.now().millisecondsSinceEpoch}';
    final now = DateTime.now();
    final title =
        '미팅 ${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')} '
        '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';

    final newMeeting = Meeting(
      id: meetingId,
      title: title,
      createdAt: now,
      status: MeetingStatus.processing,
      duration: Duration(seconds: elapsedSeconds),
      audioFilePath: filePath,
      vocabularyId: _selectedVocabularyId,
    );

    ref.read(meetingListProvider.notifier).addMeeting(newMeeting);
    ref.read(recordingProvider.notifier).reset();
    if (mounted) context.go('/processing/$meetingId');
  }

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
      appBar: AppBar(title: const Text('새 녹음')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
          child: Column(
            children: [
              const Spacer(),
              // 상태 인디케이터
              _StatusPill(isRecording: isRecording, status: state.status),
              const SizedBox(height: AppSpacing.xl),
              // 타이머
              Semantics(
                label: '경과 시간 ${_formatTime(state.elapsedSeconds)}',
                liveRegion: true,
                child: Text(_formatTime(state.elapsedSeconds), style: AppTypography.timer(context)),
              ),
              const SizedBox(height: AppSpacing.xxxl),
              // 녹음 버튼
              _RecordButton(
                isRecording: isRecording,
                scaleAnimation: _scaleAnimation,
                pulseAnimation: _pulseAnimation,
                onTap: _toggleRecording,
                onTapDown: (_) => _scaleController.reverse(),
                onTapUp: (_) => _scaleController.forward(),
                onTapCancel: () => _scaleController.forward(),
              ),
              const Spacer(),
              // 사용자 사전 선택 (녹음 전에만)
              if (!isRecording && state.status != RecordingStatus.stopped) ...[
                _buildVocabularySelector(context),
                const SizedBox(height: AppSpacing.xl),
              ] else ...[
                const SizedBox(height: AppSpacing.xxxl),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildVocabularySelector(BuildContext context) {
    final vocabAsync = ref.watch(vocabularyListProvider);
    return vocabAsync.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (vocabularies) {
        if (vocabularies.isEmpty) return const SizedBox.shrink();
        return InputDecorator(
          decoration: const InputDecoration(
            labelText: '사용자 사전 (선택)',
            prefixIcon: Icon(Icons.menu_book_outlined),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String?>(
              value: _selectedVocabularyId,
              isDense: true,
              isExpanded: true,
              hint: const Text('사전 없음'),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('사전 없음')),
                ...vocabularies.map((v) => DropdownMenuItem<String?>(
                      value: v.id,
                      child: Text('${v.name} (${v.words.length}단어)',
                          overflow: TextOverflow.ellipsis),
                    )),
              ],
              onChanged: (value) => setState(() => _selectedVocabularyId = value),
            ),
          ),
        );
      },
    );
  }
}

/// 상태 필 (녹음 중 빨강 펄스 / 대기 회색)
class _StatusPill extends StatelessWidget {
  final bool isRecording;
  final RecordingStatus status;
  const _StatusPill({required this.isRecording, required this.status});

  @override
  Widget build(BuildContext context) {
    final color = isRecording ? AppColors.error : AppColors.of(context).textTertiary;
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 250),
      child: Container(
        key: ValueKey(isRecording),
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.xs + 2),
        decoration: BoxDecoration(
          color: color.withAlpha(isRecording ? 24 : 0),
          borderRadius: AppRadius.brPill,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isRecording)
              _BlinkingDot(color: color)
            else
              Container(width: 7, height: 7, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
            const SizedBox(width: AppSpacing.sm),
            Text(
              _label(status),
              style: TextStyle(
                color: color,
                fontSize: 13,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.2,
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _label(RecordingStatus s) => switch (s) {
        RecordingStatus.idle => '탭하여 녹음 시작',
        RecordingStatus.recording => '녹음 중',
        RecordingStatus.paused => '일시 정지됨',
        RecordingStatus.stopped => '녹음 완료',
      };
}

class _BlinkingDot extends StatefulWidget {
  final Color color;
  const _BlinkingDot({required this.color});
  @override
  State<_BlinkingDot> createState() => _BlinkingDotState();
}

class _BlinkingDotState extends State<_BlinkingDot> with SingleTickerProviderStateMixin {
  late AnimationController _c;
  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat(reverse: true);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _c,
      child: Container(width: 7, height: 7, decoration: BoxDecoration(color: widget.color, shape: BoxShape.circle)),
    );
  }
}

/// 녹음 버튼 — 펄스 링 + 스케일 피드백
class _RecordButton extends StatelessWidget {
  final bool isRecording;
  final Animation<double> scaleAnimation;
  final Animation<double> pulseAnimation;
  final VoidCallback onTap;
  final void Function(TapDownDetails) onTapDown;
  final void Function(TapUpDetails) onTapUp;
  final VoidCallback onTapCancel;

  const _RecordButton({
    required this.isRecording,
    required this.scaleAnimation,
    required this.pulseAnimation,
    required this.onTap,
    required this.onTapDown,
    required this.onTapUp,
    required this.onTapCancel,
  });

  @override
  Widget build(BuildContext context) {
    final color = isRecording ? AppColors.error : AppColors.of(context).primary;

    return SizedBox(
      width: 160,
      height: 160,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // 펄스 링 (녹음 중만)
          if (isRecording)
            AnimatedBuilder(
              animation: pulseAnimation,
              builder: (_, __) {
                final t = pulseAnimation.value;
                return Container(
                  width: 120 + t * 60,
                  height: 120 + t * 60,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: color.withAlpha((120 * (1 - t)).round()), width: 2),
                  ),
                );
              },
            ),
          // 본체 버튼
          ScaleTransition(
            scale: scaleAnimation,
            child: Semantics(
              button: true,
              label: isRecording ? '녹음 중지' : '녹음 시작',
              child: Material(
                color: color,
                shape: const CircleBorder(),
                clipBehavior: Clip.antiAlias,
                elevation: isRecording ? 8 : 4,
                shadowColor: color.withAlpha(120),
                child: InkWell(
                  onTap: onTap,
                  onTapDown: onTapDown,
                  onTapUp: onTapUp,
                  onTapCancel: onTapCancel,
                  splashColor: Colors.white.withAlpha(60),
                  child: SizedBox(
                    width: 120,
                    height: 120,
                    child: Icon(
                      isRecording ? Icons.stop_rounded : Icons.mic_rounded,
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
    );
  }
}
