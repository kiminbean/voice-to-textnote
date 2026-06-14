// 화자 프로필 관리 화면 — SPEC-SPEAKER-001
// 전역/회의별 화자 프로필 조회, 생성, 수정, 삭제
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/speaker_profile.dart';
import 'package:voice_to_textnote/providers/speaker_provider.dart';
import 'package:voice_to_textnote/services/speaker_api.dart';

class SpeakerProfileScreen extends ConsumerStatefulWidget {
  final String? taskId;

  const SpeakerProfileScreen({super.key, this.taskId});

  @override
  ConsumerState<SpeakerProfileScreen> createState() =>
      _SpeakerProfileScreenState();
}

class _SpeakerProfileScreenState extends ConsumerState<SpeakerProfileScreen> {
  @override
  Widget build(BuildContext context) {
    final profilesAsync = ref.watch(speakerListProvider(widget.taskId));
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('화자 프로필'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => _showCreateDialog(context),
            tooltip: '화자 추가',
          ),
        ],
      ),
      body: profilesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('화자 프로필을 불러올 수 없습니다'),
              const SizedBox(height: 8),
              Text('$e', style: theme.textTheme.bodySmall),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: () =>
                    ref.invalidate(speakerListProvider(widget.taskId)),
                child: const Text('재시도'),
              ),
            ],
          ),
        ),
        data: (profiles) {
          if (profiles.isEmpty) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.record_voice_over_outlined,
                      size: 64, color: theme.colorScheme.outline),
                  const SizedBox(height: 16),
                  const Text('등록된 화자 프로필이 없습니다'),
                  const SizedBox(height: 8),
                  Text(
                    '오른쪽 위 + 버튼으로 화자를 추가하세요',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            );
          }

          // 전역 프로필과 회의별 프로필 분리
          final globalProfiles =
              profiles.where((p) => p.taskId == null).toList();
          final meetingProfiles =
              profiles.where((p) => p.taskId != null).toList();

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (meetingProfiles.isNotEmpty) ...[
                _sectionHeader('이 회의의 화자', theme),
                ...meetingProfiles.map((p) => _profileTile(p, theme)),
                const SizedBox(height: 24),
              ],
              if (globalProfiles.isNotEmpty) ...[
                _sectionHeader('전역 화자', theme),
                ...globalProfiles.map((p) => _profileTile(p, theme)),
              ],
            ],
          );
        },
      ),
    );
  }

  Widget _sectionHeader(String title, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: theme.textTheme.titleSmall?.copyWith(
          color: theme.colorScheme.primary,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _profileTile(SpeakerProfile profile, ThemeData theme) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: theme.colorScheme.primaryContainer,
          child: Text(
            profile.displayName.isNotEmpty
                ? profile.displayName[0].toUpperCase()
                : '?',
            style: TextStyle(color: theme.colorScheme.onPrimaryContainer),
          ),
        ),
        title: Text(profile.displayName),
        subtitle: Text(
          [
            profile.speakerLabel,
            if (profile.role != null) profile.role,
          ].join(' · '),
        ),
        trailing: PopupMenuButton<String>(
          onSelected: (action) {
            switch (action) {
              case 'edit':
                _showEditDialog(context, profile);
              case 'delete':
                _confirmDelete(context, profile);
            }
          },
          itemBuilder: (_) => [
            const PopupMenuItem(value: 'edit', child: Text('수정')),
            const PopupMenuItem(value: 'delete', child: Text('삭제')),
          ],
        ),
      ),
    );
  }

  Future<void> _showCreateDialog(BuildContext context) async {
    final result = await showDialog<_SpeakerFormData>(
      context: context,
      builder: (ctx) => const _SpeakerFormDialog(),
    );
    if (result == null) return;

    try {
      await ref.read(speakerApiProvider).create(SpeakerProfileCreate(
            speakerLabel: result.speakerLabel,
            displayName: result.displayName,
            role: result.role,
            note: result.note,
            taskId: widget.taskId,
          ));
      if (!context.mounted) return;
      ref.invalidate(speakerListProvider(widget.taskId));
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('생성 실패: $e')),
        );
      }
    }
  }

  Future<void> _showEditDialog(
      BuildContext context, SpeakerProfile profile) async {
    final result = await showDialog<_SpeakerFormData>(
      context: context,
      builder: (ctx) => _SpeakerFormDialog(
        initial: _SpeakerFormData(
          speakerLabel: profile.speakerLabel,
          displayName: profile.displayName,
          role: profile.role,
          note: profile.note,
        ),
        isEdit: true,
      ),
    );
    if (result == null) return;

    try {
      await ref.read(speakerApiProvider).update(
            profile.id,
            SpeakerProfileUpdate(
              displayName: result.displayName,
              role: result.role,
              note: result.note,
            ),
          );
      if (!context.mounted) return;
      ref.invalidate(speakerListProvider(widget.taskId));
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('수정 실패: $e')),
        );
      }
    }
  }

  Future<void> _confirmDelete(
      BuildContext context, SpeakerProfile profile) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('화자 프로필 삭제'),
        content: Text("'${profile.displayName}' 프로필을 삭제하시겠습니까?"),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('취소')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('삭제')),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      await ref.read(speakerApiProvider).delete(profile.id);
      if (!context.mounted) return;
      ref.invalidate(speakerListProvider(widget.taskId));
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('삭제 실패: $e')),
        );
      }
    }
  }
}

class _SpeakerFormData {
  final String speakerLabel;
  final String displayName;
  final String? role;
  final String? note;

  const _SpeakerFormData({
    required this.speakerLabel,
    required this.displayName,
    this.role,
    this.note,
  });
}

class _SpeakerFormDialog extends StatefulWidget {
  final _SpeakerFormData? initial;
  final bool isEdit;

  const _SpeakerFormDialog({this.initial, this.isEdit = false});

  @override
  State<_SpeakerFormDialog> createState() => _SpeakerFormDialogState();
}

class _SpeakerFormDialogState extends State<_SpeakerFormDialog> {
  late final TextEditingController _labelCtl;
  late final TextEditingController _nameCtl =
      TextEditingController(text: widget.initial?.displayName);
  late final _roleCtl = TextEditingController(text: widget.initial?.role);
  late final _noteCtl = TextEditingController(text: widget.initial?.note);

  @override
  void initState() {
    super.initState();
    _labelCtl = TextEditingController(
        text: widget.initial?.speakerLabel ?? 'SPEAKER_00');
  }

  @override
  void dispose() {
    _labelCtl.dispose();
    _nameCtl.dispose();
    _roleCtl.dispose();
    _noteCtl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.isEdit ? '화자 프로필 수정' : '화자 프로필 추가'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _labelCtl,
              decoration: const InputDecoration(
                labelText: '화자 레이블',
                hintText: 'SPEAKER_00',
              ),
              enabled: !widget.isEdit,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _nameCtl,
              decoration: const InputDecoration(
                labelText: '표시 이름 *',
                hintText: '김개발',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _roleCtl,
              decoration: const InputDecoration(
                labelText: '역할',
                hintText: '팀장, PM 등',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _noteCtl,
              decoration: const InputDecoration(
                labelText: '메모',
              ),
              maxLines: 2,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('취소'),
        ),
        FilledButton(
          onPressed: () {
            if (_nameCtl.text.trim().isEmpty) return;
            Navigator.pop(
              context,
              _SpeakerFormData(
                speakerLabel: _labelCtl.text.trim(),
                displayName: _nameCtl.text.trim(),
                role:
                    _roleCtl.text.trim().isEmpty ? null : _roleCtl.text.trim(),
                note:
                    _noteCtl.text.trim().isEmpty ? null : _noteCtl.text.trim(),
              ),
            );
          },
          child: const Text('저장'),
        ),
      ],
    );
  }
}
