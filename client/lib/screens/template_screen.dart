// 양식 관리 화면 - SPEC-TMPL-001 REQ-TMPL-005, REQ-TMPL-007
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:voice_to_textnote/models/template.dart';
import 'package:voice_to_textnote/providers/template_provider.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';

class TemplateScreen extends ConsumerWidget {
  const TemplateScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final templatesAsync = ref.watch(templateListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('양식 관리'),
        centerTitle: true,
      ),
      body: templatesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => EmptyStateWidget(
          icon: Icons.cloud_off_rounded,
          title: '양식 목록을 불러올 수 없습니다',
          subtitle: error.toString(),
          actionLabel: '다시 시도',
          onAction: () => ref.read(templateListProvider.notifier).refresh(),
        ),
        data: (templates) => templates.isEmpty
            ? const EmptyStateWidget(
                icon: Icons.folder_open_rounded,
                title: '등록된 양식이 없습니다',
                subtitle: '아래 버튼을 눌러 양식을 업로드하세요',
              )
            : _TemplateListView(templates: templates),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _pickAndUploadFile(context, ref),
        icon: const Icon(Icons.upload_file),
        label: const Text('양식 업로드'),
      ),
    );
  }

  // 파일 선택 및 업로드 처리
  Future<void> _pickAndUploadFile(BuildContext context, WidgetRef ref) async {
    // PDF 및 DOCX 파일만 허용
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'docx'],
      allowMultiple: false,
    );

    if (result == null || result.files.isEmpty) return;

    final pickedFile = result.files.first;
    if (pickedFile.path == null) return;

    final file = File(pickedFile.path!);

    try {
      // 업로드 중 로딩 표시
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('양식 업로드 중...')),
        );
      }

      await ref.read(templateListProvider.notifier).uploadTemplate(file);

      if (context.mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('양식이 성공적으로 업로드되었습니다')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('업로드 실패: ${e.toString()}'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }
}

// 양식 목록 뷰
class _TemplateListView extends ConsumerWidget {
  final List<Template> templates;

  const _TemplateListView({required this.templates});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: templates.length,
      itemBuilder: (context, index) {
        final template = templates[index];
        return _TemplateListItem(
          template: template,
          onDelete: () => _confirmDelete(context, ref, template),
        );
      },
    );
  }

  // 삭제 확인 다이얼로그
  Future<void> _confirmDelete(
    BuildContext context,
    WidgetRef ref,
    Template template,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('양식 삭제'),
        content: Text('"${template.name}" 양식을 삭제하시겠습니까?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('삭제'),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      try {
        await ref
            .read(templateListProvider.notifier)
            .deleteTemplate(template.templateId);
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('양식이 삭제되었습니다')),
          );
        }
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('삭제 실패: ${e.toString()}'),
              backgroundColor: AppColors.error,
            ),
          );
        }
      }
    }
  }
}

// 개별 양식 항목 위젯
class _TemplateListItem extends StatelessWidget {
  final Template template;
  final VoidCallback onDelete;

  const _TemplateListItem({
    required this.template,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    // 파일 형식에 따른 아이콘 및 색상 결정
    final isPdf = template.format.toLowerCase() == 'pdf';
    final formatIcon = isPdf ? Icons.picture_as_pdf : Icons.description;
    final formatColor = isPdf ? AppColors.error : AppColors.indigo600;
    final dateStr =
        DateFormat('yyyy.MM.dd HH:mm').format(template.createdAt.toLocal());

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: ListTile(
        leading: Icon(formatIcon, color: formatColor, size: 36),
        title: Text(
          template.name,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          '${template.format.toUpperCase()} · $dateStr',
          style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline),
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete_outline),
          color: Theme.of(context).colorScheme.outline,
          tooltip: '삭제',
          onPressed: onDelete,
        ),
      ),
    );
  }
}
