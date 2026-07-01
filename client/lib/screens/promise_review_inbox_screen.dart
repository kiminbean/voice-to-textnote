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
    final commandCenter = ref.watch(promiseCommandCenterProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('약속 레이더 Command Center'),
        actions: [
          IconButton(
            tooltip: '새로고침',
            onPressed: () {
              ref.invalidate(promiseCommandCenterProvider);
            },
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(promiseCommandCenterProvider);
        },
        child: commandCenter.when(
          data: (center) => _CommandCenterView(center: center),
          loading: () => ListView(
            padding: const EdgeInsets.all(AppSpacing.xl),
            children: const [
              Center(child: CircularProgressIndicator()),
            ],
          ),
          error: (error, _) => ListView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            children: [
              _ErrorState(
                message: 'Command Center를 불러올 수 없습니다.',
                detail: error.toString(),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CommandCenterView extends StatelessWidget {
  final PromiseCommandCenter center;

  const _CommandCenterView({required this.center});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        _FocusItemsPanel(items: center.focusItems),
        const SizedBox(height: AppSpacing.md),
        _LearningInsightHeader(insight: center.learningInsight),
        const SizedBox(height: AppSpacing.md),
        _ReviewQueueList(queue: center.reviewQueue),
        const SizedBox(height: AppSpacing.md),
        _EvidenceAuditPanel(audit: center.evidenceAudit),
        const SizedBox(height: AppSpacing.md),
        _DigestBriefPanel(
          digest: center.digest,
          brief: center.preMeetingBrief,
        ),
        const SizedBox(height: AppSpacing.md),
        _ExternalTaskPanel(
          report: center.externalReconcile,
          oauth: center.googleTasksOAuth,
        ),
        const SizedBox(height: AppSpacing.md),
        _AccuracyPanel(report: center.accuracyReport),
      ],
    );
  }
}

class _FocusItemsPanel extends StatelessWidget {
  final List<PromiseCommandCenterFocusItem> items;

  const _FocusItemsPanel({required this.items});

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
                Icon(Icons.radar_rounded, color: scheme.primary),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    '오늘 볼 항목',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            if (items.isEmpty)
              Text('즉시 처리할 약속 항목이 없습니다.', style: theme.textTheme.bodySmall)
            else
              for (final item in items.take(5)) ...[
                _FocusItemRow(item: item),
                const SizedBox(height: AppSpacing.xs),
              ],
          ],
        ),
      ),
    );
  }
}

class _FocusItemRow extends StatelessWidget {
  final PromiseCommandCenterFocusItem item;

  const _FocusItemRow({required this.item});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = switch (item.severity) {
      'critical' => AppColors.error,
      'high' => AppColors.warning,
      'warning' => AppColors.warning,
      _ => Theme.of(context).colorScheme.primary,
    };
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.priority_high_rounded, size: 18, color: color),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${item.label} ${item.count}',
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              Text(item.action, style: theme.textTheme.bodySmall),
            ],
          ),
        ),
      ],
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
                  icon: Icons.hub_outlined,
                  label: 'Alias ${insight.aliasGraphSize}',
                ),
                _MetricChip(
                  icon: insight.evidenceLockEnabled
                      ? Icons.lock_outline_rounded
                      : Icons.lock_open_rounded,
                  label: insight.evidenceLockEnabled ? '근거 잠금' : '근거 확인',
                ),
                _MetricChip(
                  icon: Icons.tune_rounded,
                  label: insight.recommendedPolicy,
                ),
              ],
            ),
            if (insight.statusFalsePositiveRate.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  for (final entry
                      in insight.statusFalsePositiveRate.entries.take(4))
                    _MetricChip(
                      icon: Icons.percent_rounded,
                      label: '${entry.key} ${(entry.value * 100).round()}%',
                    ),
                ],
              ),
            ],
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

class _EvidenceAuditPanel extends StatelessWidget {
  final PromiseEvidenceAuditSummary audit;

  const _EvidenceAuditPanel({required this.audit});

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
              'Evidence Audit',
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
                  icon: Icons.lock_outline_rounded,
                  label: '잠금 ${audit.lockedCount}',
                ),
                _MetricChip(
                  icon: Icons.warning_amber_rounded,
                  label: '약함 ${audit.weakEvidenceCount}',
                ),
                _MetricChip(
                  icon: Icons.schedule_rounded,
                  label: '시간 없음 ${audit.missingTimestampCount}',
                ),
                _MetricChip(
                  icon: Icons.record_voice_over_outlined,
                  label: '화자 없음 ${audit.missingSpeakerCount}',
                ),
                _MetricChip(
                  icon: Icons.rule_rounded,
                  label: '근거 ${(audit.averageSimilarity * 100).round()}%',
                ),
              ],
            ),
            for (final note in audit.notes.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(note, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _DigestBriefPanel extends StatelessWidget {
  final PromiseDigest digest;
  final PromisePreMeetingBrief brief;

  const _DigestBriefPanel({
    required this.digest,
    required this.brief,
  });

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
              digest.title,
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
                  icon: Icons.pending_actions_rounded,
                  label: '열림 ${digest.openCount}',
                ),
                _MetricChip(
                  icon: Icons.event_busy_rounded,
                  label: '초과 ${digest.overdueCount}',
                ),
                _MetricChip(
                  icon: Icons.priority_high_rounded,
                  label: '고위험 ${digest.highRiskCount}',
                ),
                _MetricChip(
                  icon: Icons.fact_check_outlined,
                  label: '준비 ${brief.readinessScore}',
                ),
              ],
            ),
            for (final checkpoint in brief.checkpoints.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(checkpoint, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _ExternalTaskPanel extends StatelessWidget {
  final PromiseExternalTaskReconcileResponse report;
  final PromiseGoogleTasksOAuthGuide oauth;

  const _ExternalTaskPanel({
    required this.report,
    required this.oauth,
  });

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
            if (report.requiresOauth) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Scope: ${oauth.scope}',
                style: theme.textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              for (final step in oauth.steps.take(2)) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(step, style: theme.textTheme.bodySmall),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _AccuracyPanel extends StatelessWidget {
  final PromiseAccuracyReport report;

  const _AccuracyPanel({required this.report});

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
              '정확도 기준선',
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
                  icon: Icons.analytics_outlined,
                  label: '${(report.evaluation.accuracy * 100).round()}%',
                ),
                _MetricChip(
                  icon: Icons.library_books_outlined,
                  label: 'Case ${report.evaluation.caseCount}',
                ),
                _MetricChip(
                  icon: Icons.mic_external_on_outlined,
                  label:
                      '실제 ${report.realMeetingCaseCount}/${report.targetCaseCount}',
                ),
                _MetricChip(
                  icon: Icons.warning_amber_rounded,
                  label: '경고 ${report.qualityWarnings.length}',
                ),
              ],
            ),
            for (final warning in report.qualityWarnings.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(warning, style: theme.textTheme.bodySmall),
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
