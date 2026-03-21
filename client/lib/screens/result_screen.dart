// 결과 화면 - 실제 API 데이터 바인딩 + 에러/빈 상태
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/providers/result_provider.dart';
import 'package:voice_to_textnote/widgets/error_retry_widget.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';
import 'package:voice_to_textnote/widgets/shimmer_text.dart';
import 'package:voice_to_textnote/widgets/speaker_segment.dart';

class ResultScreen extends ConsumerWidget {
  final String meetingId;

  const ResultScreen({super.key, required this.meetingId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('회의 결과'),
          bottom: const TabBar(
            tabs: [
              Tab(text: '회의록'),
              Tab(text: 'AI 요약'),
              Tab(text: '액션 아이템'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            // 회의록 탭
            _TranscriptTab(meetingId: meetingId),
            // AI 요약 탭
            _SummaryTab(meetingId: meetingId),
            // 액션 아이템 탭
            _ActionItemsTab(meetingId: meetingId),
          ],
        ),
      ),
    );
  }
}

// 회의록 탭
class _TranscriptTab extends ConsumerWidget {
  final String meetingId;

  const _TranscriptTab({required this.meetingId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resultAsync = ref.watch(resultProvider(meetingId));

    return resultAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: '회의록을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(resultProvider(meetingId)),
      ),
      data: (result) {
        if (result.minutes.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.article_outlined,
            title: '회의록이 없습니다',
            subtitle: '처리가 완료되지 않았을 수 있습니다',
          );
        }

        // 회의록 텍스트를 세그먼트로 파싱하여 표시
        // MVP: 단일 텍스트 블록으로 표시
        return ListView(
          children: [
            SpeakerSegment(
              speakerName: '회의록',
              text: result.minutes,
              startTime: Duration.zero,
              speakerIndex: 0,
            ),
          ],
        );
      },
    );
  }

  // shimmer 로딩 스켈레톤
  Widget _buildShimmerLoading() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: List.generate(
          4,
          (_) => const Padding(
            padding: EdgeInsets.only(bottom: 16),
            child: ShimmerText(lines: 4),
          ),
        ),
      ),
    );
  }
}

// AI 요약 탭
class _SummaryTab extends ConsumerWidget {
  final String meetingId;

  const _SummaryTab({required this.meetingId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resultAsync = ref.watch(resultProvider(meetingId));

    return resultAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: 'AI 요약을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(resultProvider(meetingId)),
      ),
      data: (result) {
        if (result.summary.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.summarize_outlined,
            title: 'AI 요약이 없습니다',
          );
        }

        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'AI 요약',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const Divider(),
                  Text(
                    result.summary,
                    style: const TextStyle(height: 1.6),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildShimmerLoading() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const ShimmerText(lines: 1),
              const SizedBox(height: 16),
              const Divider(),
              const SizedBox(height: 8),
              const ShimmerText(lines: 5),
            ],
          ),
        ),
      ),
    );
  }
}

// 액션 아이템 탭
class _ActionItemsTab extends ConsumerWidget {
  final String meetingId;

  const _ActionItemsTab({required this.meetingId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resultAsync = ref.watch(resultProvider(meetingId));

    return resultAsync.when(
      loading: () => _buildShimmerLoading(),
      error: (error, _) => ErrorRetryWidget(
        message: '액션 아이템을 불러올 수 없습니다',
        onRetry: () => ref.invalidate(resultProvider(meetingId)),
      ),
      data: (result) {
        if (result.actionItems.isEmpty) {
          return const EmptyStateWidget(
            icon: Icons.checklist_outlined,
            title: '액션 아이템이 없습니다',
          );
        }

        return _ActionItemsList(items: result.actionItems);
      },
    );
  }

  Widget _buildShimmerLoading() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: List.generate(
          3,
          (_) => const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: ShimmerText(lines: 1),
          ),
        ),
      ),
    );
  }
}

// 액션 아이템 목록 (체크박스)
class _ActionItemsList extends StatefulWidget {
  final List<String> items;

  const _ActionItemsList({required this.items});

  @override
  State<_ActionItemsList> createState() => _ActionItemsListState();
}

class _ActionItemsListState extends State<_ActionItemsList> {
  late final List<bool> _checked;

  @override
  void initState() {
    super.initState();
    _checked = List.filled(widget.items.length, false);
  }

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: widget.items.length,
      itemBuilder: (context, index) {
        final text = widget.items[index];
        final done = _checked[index];
        return CheckboxListTile(
          value: done,
          title: Text(
            text,
            style: TextStyle(
              decoration: done ? TextDecoration.lineThrough : null,
              color: done ? Colors.grey : null,
            ),
          ),
          onChanged: (value) {
            setState(() {
              _checked[index] = value ?? false;
            });
          },
        );
      },
    );
  }
}
