import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:voice_to_textnote/models/vocabulary.dart';
import 'package:voice_to_textnote/providers/vocabulary_provider.dart';

class VocabularyScreen extends ConsumerWidget {
  const VocabularyScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final vocabulariesAsync = ref.watch(vocabularyListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('사용자 사전 관리'),
        centerTitle: true,
      ),
      body: vocabulariesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _VocabularyErrorView(
          error: error.toString(),
          onRetry: () => ref.read(vocabularyListProvider.notifier).refresh(),
        ),
        data: (vocabularies) => RefreshIndicator(
          onRefresh: () => ref.read(vocabularyListProvider.notifier).refresh(),
          child: vocabularies.isEmpty
              ? const _VocabularyEmptyView()
              : _VocabularyListView(
                  vocabularies: vocabularies,
                  onEdit: (vocabulary) => _showVocabularyDialog(context, ref, vocabulary: vocabulary),
                ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showVocabularyDialog(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('사전 추가'),
      ),
    );
  }

  Future<void> _showVocabularyDialog(BuildContext context, WidgetRef ref, {Vocabulary? vocabulary}) async {
    final nameController = TextEditingController(text: vocabulary?.name ?? '');
    final wordsController = TextEditingController(text: vocabulary?.words.join(', ') ?? '');
    final isEdit = vocabulary != null;

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(isEdit ? '사전 수정' : '새 사전 추가'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameController,
                decoration: const InputDecoration(
                  labelText: '사전 이름',
                  hintText: '예: IT 용어, 의학 용어',
                ),
                autofocus: !isEdit,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: wordsController,
                decoration: const InputDecoration(
                  labelText: '단어 목록 (쉼표로 구분)',
                  hintText: '예: 쿠버네티스, 도커, 마이크로서비스',
                ),
                maxLines: 3,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          ElevatedButton(
            onPressed: () {
              if (nameController.text.trim().isEmpty || wordsController.text.trim().isEmpty) {
                ScaffoldMessenger.of(ctx).showSnackBar(
                  const SnackBar(content: Text('이름과 단어 목록을 모두 입력해주세요.')),
                );
                return;
              }
              Navigator.of(ctx).pop(true);
            },
            child: Text(isEdit ? '수정' : '추가'),
          ),
        ],
      ),
    );

    if (result == true && context.mounted) {
      final name = nameController.text.trim();
      final words = wordsController.text
          .split(',')
          .map((w) => w.trim())
          .where((w) => w.isNotEmpty)
          .toList();

      try {
        if (isEdit) {
          await ref.read(vocabularyListProvider.notifier).updateVocabulary(vocabulary.id, name, words);
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('사전이 수정되었습니다')),
            );
          }
        } else {
          await ref.read(vocabularyListProvider.notifier).createVocabulary(name, words);
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('새 사전이 추가되었습니다')),
            );
          }
        }
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('${isEdit ? '수정' : '추가'} 실패: ${e.toString()}'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    }
  }
}

class _VocabularyListView extends ConsumerWidget {
  final List<Vocabulary> vocabularies;
  final void Function(Vocabulary) onEdit;

  const _VocabularyListView({
    required this.vocabularies,
    required this.onEdit,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: vocabularies.length,
      itemBuilder: (context, index) {
        final vocabulary = vocabularies[index];
        return _VocabularyListItem(
          vocabulary: vocabulary,
          onEdit: () => onEdit(vocabulary),
          onDelete: () => _confirmDelete(context, ref, vocabulary),
        );
      },
    );
  }

  Future<void> _confirmDelete(
    BuildContext context,
    WidgetRef ref,
    Vocabulary vocabulary,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('사전 삭제'),
        content: Text('"${vocabulary.name}" 사전을 삭제하시겠습니까?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('삭제'),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      try {
        await ref
            .read(vocabularyListProvider.notifier)
            .deleteVocabulary(vocabulary.id);
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('사전이 삭제되었습니다')),
          );
        }
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('삭제 실패: ${e.toString()}'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    }
  }
}

class _VocabularyListItem extends StatelessWidget {
  final Vocabulary vocabulary;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  const _VocabularyListItem({
    required this.vocabulary,
    required this.onEdit,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final dateStr = DateFormat('yyyy.MM.dd HH:mm').format(vocabulary.createdAt.toLocal());

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: ListTile(
        leading: const CircleAvatar(
          child: Icon(Icons.book),
        ),
        title: Text(
          vocabulary.name,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          '단어 ${vocabulary.words.length}개 · $dateStr',
          style: const TextStyle(fontSize: 12, color: Colors.grey),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.edit_outlined),
              color: Colors.blue,
              tooltip: '수정',
              onPressed: onEdit,
            ),
            IconButton(
              icon: const Icon(Icons.delete_outline),
              color: Colors.red,
              tooltip: '삭제',
              onPressed: onDelete,
            ),
          ],
        ),
        onTap: onEdit,
      ),
    );
  }
}

class _VocabularyEmptyView extends StatelessWidget {
  const _VocabularyEmptyView();

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: const [
        SizedBox(height: 100),
        Icon(Icons.menu_book, size: 64, color: Colors.grey),
        SizedBox(height: 16),
        Text(
          '등록된 사용자 사전이 없습니다',
          style: TextStyle(color: Colors.grey, fontSize: 16),
          textAlign: TextAlign.center,
        ),
        SizedBox(height: 8),
        Text(
          '아래 버튼을 눌러 새 사전을 추가하세요',
          style: TextStyle(color: Colors.grey, fontSize: 14),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}

class _VocabularyErrorView extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;

  const _VocabularyErrorView({required this.error, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 64, color: Colors.red),
          const SizedBox(height: 16),
          const Text(
            '사전 목록을 불러올 수 없습니다',
            style: TextStyle(fontSize: 16),
          ),
          const SizedBox(height: 8),
          Text(
            error,
            style: const TextStyle(color: Colors.grey, fontSize: 12),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: onRetry,
            child: const Text('다시 시도'),
          ),
        ],
      ),
    );
  }
}
