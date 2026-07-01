import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/promise_radar.dart';
import 'package:voice_to_textnote/providers/result_provider.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';

class PromiseReviewInboxScreen extends ConsumerWidget {
  const PromiseReviewInboxScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final inbox = ref.watch(promiseAutopilotReviewInboxProvider);
    final learning = ref.watch(promiseLearningInsightProvider);
    final reconcile = ref.watch(promiseExternalTaskReconcileProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('약속 레이더 검토함'),
        actions: [
          IconButton(
            tooltip: '새로고침',
            onPressed: () {
              ref.invalidate(promiseAutopilotReviewInboxProvider);
              ref.invalidate(promiseLearningInsightProvider);
              ref.invalidate(promiseExternalTaskReconcileProvider);
            },
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(promiseAutopilotReviewInboxProvider);
          ref.invalidate(promiseLearningInsightProvider);
          ref.invalidate(promiseExternalTaskReconcileProvider);
        },
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          children: [
            learning.maybeWhen(
              data: (value) => _LearningInsightHeader(insight: value),
              orElse: () => const SizedBox.shrink(),
            ),
            const SizedBox(height: AppSpacing.md),
            inbox.when(
              data: (queue) => _ReviewQueueList(queue: queue),
              loading: () => const Center(
                child: Padding(
                  padding: EdgeInsets.all(AppSpacing.xl),
                  child: CircularProgressIndicator(),
                ),
              ),
              error: (error, _) => _ErrorState(
                message: '검토함을 불러올 수 없습니다.',
                detail: error.toString(),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            reconcile.maybeWhen(
              data: (value) => _ExternalTaskPanel(report: value),
              orElse: () => const SizedBox.shrink(),
            ),
          ],
        ),
      ),
    );
  }
}

class _LearningInsightHeader extends StatelessWidget {
  final PromiseLearningInsight insight;

  const _LearningInsightHeader({required this.insight});

  @override
  Widget build(BuildContext context) {
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
                Icon(Icons.psychology_alt_outlined, color: scheme.primary),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    '학습 루프',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                Text(
                  '${(insight.autopilotThreshold * 100).round()}%',
                  style: theme.textTheme.labelLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.xs,
              children: [
                _MetricChip(
                  icon: Icons.verified_outlined,
                  label: '확정 ${insight.confirmedCount}',
                ),
                _MetricChip(
                  icon: Icons.report_gmailerrorred_outlined,
                  label: '오판 ${insight.falsePositiveCount}',
                ),
                _MetricChip(
                  icon: Icons.person_search_outlined,
                  label: '담당자 ${insight.assigneeCorrectionCount}',
                ),
                _MetricChip(
                  icon: Icons.tune_rounded,
                  label: insight.recommendedPolicy,
                ),
              ],
            ),
            for (final action in insight.nextActions.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(action, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _ReviewQueueList extends StatelessWidget {
  final PromiseAutopilotReviewQueue queue;

  const _ReviewQueueList({required this.queue});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (queue.items.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Text(
            '확정 대기 중인 자동 판정이 없습니다.',
            style: theme.textTheme.bodyMedium,
          ),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '확정 대기 ${queue.queueCount}개 · 충돌 ${queue.conflictCount}개',
          style: theme.textTheme.titleSmall?.copyWith(
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        for (final item in queue.items) ...[
          _ReviewQueueTile(item: item),
          const SizedBox(height: AppSpacing.sm),
        ],
      ],
    );
  }
}

class _ReviewQueueTile extends StatelessWidget {
  final PromiseAutopilotReviewItem item;

  const _ReviewQueueTile({required this.item});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final assessment = item.assessment;
    final matchedTaskId = assessment.explanation.matchedTaskId;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  assessment.conflictDetected
                      ? Icons.warning_amber_rounded
                      : Icons.rule_rounded,
                  color: assessment.conflictDetected
                      ? AppColors.warning
                      : AppColors.success,
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    item.ledgerEntry.text,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              '${assessment.previousStatus} → ${assessment.suggestedStatus} · ${(assessment.confidence * 100).round()}%',
              style: theme.textTheme.bodySmall,
            ),
            if (assessment.explanation.matchedText?.isNotEmpty ?? false) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                assessment.explanation.matchedText!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: AppSpacing.sm),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: matchedTaskId == null || matchedTaskId.isEmpty
                    ? null
                    : () => context.go('/result/$matchedTaskId'),
                icon: const Icon(Icons.open_in_new_rounded),
                label: const Text('근거 열기'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ExternalTaskPanel extends StatelessWidget {
  final PromiseExternalTaskReconcileResponse report;

  const _ExternalTaskPanel({required this.report});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Google Tasks 연결',
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.xs,
              children: [
                _MetricChip(
                  icon: Icons.link_rounded,
                  label: '연결 ${report.linkedCount}',
                ),
                _MetricChip(
                  icon: Icons.sync_problem_rounded,
                  label: '재확인 ${report.needsSyncCount}',
                ),
                if (report.requiresOauth)
                  const _MetricChip(
                    icon: Icons.lock_outline_rounded,
                    label: 'OAuth 필요',
                  ),
              ],
            ),
            for (final item in report.items.take(3)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                '${item.ledgerEntry.text} · ${item.issue ?? item.direction}',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _MetricChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _MetricChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: Icon(icon, size: 16),
      label: Text(label),
      visualDensity: VisualDensity.compact,
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final String detail;

  const _ErrorState({required this.message, required this.detail});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              message,
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              detail,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
