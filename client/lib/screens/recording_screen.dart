// 녹음 화면 — 모던 미니멀 (펄스 애니메이션 + 모노스페이스 타이머)
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/meeting.dart';
import 'package:voice_to_textnote/models/promise_radar.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/providers/recording_provider.dart';
import 'package:voice_to_textnote/providers/result_provider.dart';
import 'package:voice_to_textnote/providers/vocabulary_provider.dart';
import 'package:voice_to_textnote/providers/notification_provider.dart';
import 'package:voice_to_textnote/services/permission_service.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';
import 'package:voice_to_textnote/theme/app_typography.dart';
import 'package:voice_to_textnote/utils/file_validator.dart';
import 'package:voice_to_textnote/widgets/permission_dialog.dart';
import 'package:voice_to_textnote/widgets/recording_recovery_dialog.dart';

enum CaptureMode { recording, upload, meeting }

class RecordingScreen extends ConsumerStatefulWidget {
  final CaptureMode initialMode;

  const RecordingScreen({
    super.key,
    this.initialMode = CaptureMode.recording,
  });

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
  late CaptureMode _selectedMode;
  String? _selectedVocabularyId;
  bool _isPermissionChecked = false;

  @override
  void initState() {
    super.initState();
    _selectedMode = widget.initialMode;
    WidgetsBinding.instance.addObserver(this);
    _scaleController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 150),
      lowerBound: 0.9,
      upperBound: 1.0,
      value: 1.0,
    );
    _scaleAnimation =
        CurvedAnimation(parent: _scaleController, curve: Curves.easeInOut);
    // 녹음 중 펄스 링
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    );
    _pulseAnimation =
        CurvedAnimation(parent: _pulseController, curve: Curves.easeOut);
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
              ref
                  .read(recordingProvider.notifier)
                  .discardInterruptedRecording();
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
    final preMeetingBrief = ref.watch(promisePreMeetingBriefProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('AI 녹음')),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.lg,
                  AppSpacing.sm,
                  AppSpacing.lg,
                  AppSpacing.xl,
                ),
                child: Column(
                  children: [
                    _CaptureModeStrip(
                      selectedMode: _selectedMode,
                      onRecordingTap: () {
                        setState(() => _selectedMode = CaptureMode.recording);
                      },
                      onImportTap: () {
                        setState(() => _selectedMode = CaptureMode.upload);
                        _pickAudioFile();
                      },
                      onMeetingTap: () {
                        setState(() => _selectedMode = CaptureMode.meeting);
                        _showMeetingLinkSheet();
                      },
                    ),
                    if (!isRecording) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _PreMeetingPromiseBrief(brief: preMeetingBrief),
                    ],
                    if (_selectedMode == CaptureMode.upload) ...[
                      const SizedBox(height: AppSpacing.sm),
                      const _CaptureModeHint(
                        icon: Icons.upload_file_rounded,
                        title: '업로드할 파일 선택',
                        subtitle: 'WAV, MP3, M4A, MP4, OGG 파일을 바로 처리합니다.',
                      ),
                    ],
                    const SizedBox(height: AppSpacing.lg),
                    _StatusPill(isRecording: isRecording, status: state.status),
                    const SizedBox(height: AppSpacing.xl),
                    Semantics(
                      label: '경과 시간 ${_formatTime(state.elapsedSeconds)}',
                      liveRegion: true,
                      child: Text(_formatTime(state.elapsedSeconds),
                          style: AppTypography.timer(context)),
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    _RecordButton(
                      isRecording: isRecording,
                      scaleAnimation: _scaleAnimation,
                      pulseAnimation: _pulseAnimation,
                      onTap: _toggleRecording,
                      onTapDown: (_) => _scaleController.reverse(),
                      onTapUp: (_) => _scaleController.forward(),
                      onTapCancel: () => _scaleController.forward(),
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    _LiveTranscriptPreview(isRecording: isRecording),
                  ],
                ),
              ),
            ),
            // 사용자 사전 선택 (하단 고정, 녹음 전에만)
            if (!isRecording && state.status != RecordingStatus.stopped)
              Padding(
                padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.xl, vertical: AppSpacing.lg),
                child: _buildVocabularySelector(context),
              )
            else
              const SizedBox(height: AppSpacing.xxxl),
          ],
        ),
      ),
    );
  }

  Future<void> _pickAudioFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['wav', 'mp3', 'm4a', 'mp4', 'ogg'],
      allowMultiple: false,
      withData: false,
    );
    if (!mounted || result == null) return;

    final file = result.files.single;
    final path = file.path;
    if (path == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('선택한 파일 경로를 확인할 수 없습니다.')),
      );
      return;
    }

    final validation = await validateAudioFile(path);
    if (!mounted) return;
    if (!validation.isValid) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(validation.errorMessage ?? '지원하지 않는 파일입니다.')),
      );
      return;
    }

    await _createImportedMeetingAndNavigate(path, file.name);
  }

  Future<void> _createImportedMeetingAndNavigate(
    String filePath,
    String fileName,
  ) async {
    final meetingId = 'meeting_${DateTime.now().millisecondsSinceEpoch}';
    final title = fileName.trim().isEmpty ? '업로드한 오디오' : fileName;
    final now = DateTime.now();

    final newMeeting = Meeting(
      id: meetingId,
      title: title,
      createdAt: now,
      status: MeetingStatus.processing,
      audioFilePath: filePath,
      vocabularyId: _selectedVocabularyId,
    );

    ref.read(meetingListProvider.notifier).addMeeting(newMeeting);
    if (mounted) context.go('/processing/$meetingId');
  }

  void _showMeetingLinkSheet() {
    var draftUrl = '';
    String? errorText;
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
          left: AppSpacing.lg,
          right: AppSpacing.lg,
          top: AppSpacing.sm,
          bottom: MediaQuery.of(ctx).viewInsets.bottom + AppSpacing.xl,
        ),
        child: StatefulBuilder(
          builder: (ctx, setSheetState) {
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '온라인 회의 기록',
                  style: Theme.of(ctx).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: AppSpacing.md),
                TextField(
                  decoration: InputDecoration(
                    prefixIcon: const Icon(Icons.link_rounded),
                    labelText: '회의 링크 붙여넣기',
                    hintText: 'Zoom, Google Meet, Microsoft Teams',
                    errorText: errorText,
                  ),
                  keyboardType: TextInputType.url,
                  textInputAction: TextInputAction.done,
                  onChanged: (value) {
                    draftUrl = value;
                    if (errorText != null) {
                      setSheetState(() => errorText = null);
                    }
                  },
                ),
                const SizedBox(height: AppSpacing.lg),
                FilledButton.icon(
                  onPressed: () {
                    final url = draftUrl.trim();
                    final validationError = _validateMeetingUrl(url);
                    if (validationError != null) {
                      setSheetState(() => errorText = validationError);
                      return;
                    }

                    final meeting = _createOnlineMeeting(url);
                    Navigator.of(ctx).pop();
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('${meeting.title}이 준비되었습니다.')),
                    );
                    context.go('/');
                  },
                  icon: const Icon(Icons.smart_toy_outlined),
                  label: const Text('AI 기록 봇 준비'),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Meeting _createOnlineMeeting(String sourceUrl) {
    final now = DateTime.now();
    final meeting = Meeting(
      id: 'meeting_${now.millisecondsSinceEpoch}',
      title: _onlineMeetingTitle(sourceUrl),
      createdAt: now,
      status: MeetingStatus.scheduled,
      sourceUrl: sourceUrl,
      vocabularyId: _selectedVocabularyId,
    );
    ref.read(meetingListProvider.notifier).addMeeting(meeting);
    return meeting;
  }

  String? _validateMeetingUrl(String url) {
    if (url.isEmpty) return '회의 링크를 입력해주세요';
    final uri = Uri.tryParse(url);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
      return '올바른 회의 링크를 입력해주세요';
    }
    final host = uri.host.toLowerCase();
    final supported = host.contains('zoom.us') ||
        host.contains('meet.google.com') ||
        host.contains('teams.microsoft.com');
    return supported ? null : 'Zoom, Google Meet, Teams 링크만 지원합니다';
  }

  String _onlineMeetingTitle(String url) {
    final host = Uri.tryParse(url)?.host.toLowerCase() ?? '';
    if (host.contains('zoom.us')) return 'Zoom 회의';
    if (host.contains('meet.google.com')) return 'Google Meet 회의';
    if (host.contains('teams.microsoft.com')) return 'Microsoft Teams 회의';
    return '온라인 회의';
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
                const DropdownMenuItem<String?>(
                    value: null, child: Text('사전 없음')),
                ...vocabularies.map((v) => DropdownMenuItem<String?>(
                      value: v.id,
                      child: Text('${v.name} (${v.words.length}단어)',
                          overflow: TextOverflow.ellipsis),
                    )),
              ],
              onChanged: (value) =>
                  setState(() => _selectedVocabularyId = value),
            ),
          ),
        );
      },
    );
  }
}

class _CaptureModeStrip extends StatelessWidget {
  final CaptureMode selectedMode;
  final VoidCallback onRecordingTap;
  final VoidCallback onImportTap;
  final VoidCallback onMeetingTap;

  const _CaptureModeStrip({
    required this.selectedMode,
    required this.onRecordingTap,
    required this.onImportTap,
    required this.onMeetingTap,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xs),
      decoration: BoxDecoration(
        color: scheme.surfaceAlt,
        borderRadius: AppRadius.brPill,
      ),
      child: Row(
        children: [
          Expanded(
            child: _ModeChip(
              icon: Icons.mic_rounded,
              label: '녹음',
              selected: selectedMode == CaptureMode.recording,
              onTap: onRecordingTap,
            ),
          ),
          Expanded(
            child: _ModeChip(
              icon: Icons.upload_file_rounded,
              label: '업로드',
              selected: selectedMode == CaptureMode.upload,
              onTap: onImportTap,
            ),
          ),
          Expanded(
            child: _ModeChip(
              icon: Icons.video_call_rounded,
              label: '회의 링크',
              selected: selectedMode == CaptureMode.meeting,
              onTap: onMeetingTap,
            ),
          ),
        ],
      ),
    );
  }
}

class _CaptureModeHint extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;

  const _CaptureModeHint({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: scheme.primarySoft,
        borderRadius: AppRadius.brMd,
        border: Border.all(color: scheme.primary.withAlpha(70)),
      ),
      child: Row(
        children: [
          Icon(icon, color: scheme.primary),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: scheme.textPrimary,
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: scheme.textSecondary,
                        height: 1.35,
                      ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ModeChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _ModeChip({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    return Material(
      color: selected ? scheme.surface : Colors.transparent,
      borderRadius: AppRadius.brPill,
      child: InkWell(
        borderRadius: AppRadius.brPill,
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.sm,
            vertical: AppSpacing.sm,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon,
                  size: 17,
                  color: selected ? scheme.primary : scheme.textSecondary),
              const SizedBox(width: AppSpacing.xs),
              Flexible(
                child: Text(
                  label,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: selected
                            ? scheme.textPrimary
                            : scheme.textSecondary,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LiveTranscriptPreview extends StatelessWidget {
  final bool isRecording;

  const _LiveTranscriptPreview({required this.isRecording});

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    final lines = isRecording
        ? const [
            ('Speaker 1', '이번 분기 출시 일정은 유지하고 디자인 검토를 금요일까지 마칩니다.'),
            ('Speaker 2', '액션 아이템은 담당자와 마감일 기준으로 자동 정리하겠습니다.'),
            ('AI', '요약 초안을 생성 중입니다...'),
          ]
        : const [
            ('AI', '조용한 백그라운드 녹음을 시작하면 전사가 여기에 실시간으로 표시됩니다.'),
            ('Tip', '회의가 끝나면 요약, 결정 사항, 액션 아이템을 바로 확인하세요.'),
          ];

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: AppRadius.brLg,
        border: Border.all(color: scheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.subject_rounded, color: scheme.primary),
              const SizedBox(width: AppSpacing.sm),
              Text(
                'Live Transcript',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const Spacer(),
              if (isRecording) const _BlinkingDot(color: AppColors.error),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          ...lines.map(
            (line) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.md),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 28,
                    height: 28,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: line.$1 == 'AI'
                          ? scheme.primarySoft
                          : scheme.surfaceAlt,
                      shape: BoxShape.circle,
                    ),
                    child: Text(
                      line.$1.characters.first,
                      style: TextStyle(
                        color: line.$1 == 'AI'
                            ? scheme.primary
                            : scheme.textSecondary,
                        fontWeight: FontWeight.w800,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(line.$1,
                            style: Theme.of(context)
                                .textTheme
                                .labelMedium
                                ?.copyWith(
                                  color: scheme.textSecondary,
                                  fontWeight: FontWeight.w700,
                                )),
                        const SizedBox(height: 2),
                        Text(
                          line.$2,
                          style:
                              Theme.of(context).textTheme.bodyMedium?.copyWith(
                                    height: 1.35,
                                  ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
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
    final color =
        isRecording ? AppColors.error : AppColors.of(context).textTertiary;
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 250),
      child: Container(
        key: ValueKey(isRecording),
        padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md, vertical: AppSpacing.xs + 2),
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
              Container(
                  width: 7,
                  height: 7,
                  decoration:
                      BoxDecoration(color: color, shape: BoxShape.circle)),
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

class _PreMeetingPromiseBrief extends StatelessWidget {
  final AsyncValue<PromisePreMeetingBrief> brief;

  const _PreMeetingPromiseBrief({required this.brief});

  @override
  Widget build(BuildContext context) {
    return brief.maybeWhen(
      data: (value) {
        if (value.promises.isEmpty && value.questions.isEmpty) {
          return const SizedBox.shrink();
        }
        final theme = Theme.of(context);
        final scheme = AppColors.of(context);
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.radar_outlined, color: scheme.primary),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Text(
                        value.title,
                        style: theme.textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    Text(
                      '${value.readinessScore}%',
                      style: theme.textTheme.labelLarge?.copyWith(
                        color: value.readinessScore < 70
                            ? AppColors.warning
                            : AppColors.success,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(value.summary, style: theme.textTheme.bodySmall),
                for (final promise in value.promises.take(3)) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.checklist_outlined, size: 16),
                      const SizedBox(width: AppSpacing.xs),
                      Expanded(
                        child: Text(
                          '${promise.owner ?? '미지정'} · ${promise.text}',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                    ],
                  ),
                ],
                for (final question in value.questions.take(2)) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    question,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.textSecondary,
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
      orElse: () => const SizedBox.shrink(),
    );
  }
}

class _BlinkingDot extends StatefulWidget {
  final Color color;
  const _BlinkingDot({required this.color});
  @override
  State<_BlinkingDot> createState() => _BlinkingDotState();
}

class _BlinkingDotState extends State<_BlinkingDot>
    with SingleTickerProviderStateMixin {
  late AnimationController _c;
  @override
  void initState() {
    super.initState();
    _c = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 900))
      ..repeat(reverse: true);
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
      child: Container(
          width: 7,
          height: 7,
          decoration:
              BoxDecoration(color: widget.color, shape: BoxShape.circle)),
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
                    border: Border.all(
                        color: color.withAlpha((120 * (1 - t)).round()),
                        width: 2),
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
