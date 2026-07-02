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
        _CommandCenterActionsPanel(actions: center.actions),
        const SizedBox(height: AppSpacing.md),
        _LearningInsightHeader(insight: center.learningInsight),
        const SizedBox(height: AppSpacing.md),
        _LearningTelemetryPanel(report: center.learningTelemetry),
        const SizedBox(height: AppSpacing.md),
        _LiveCoachPanel(coach: center.liveCoach),
        const SizedBox(height: AppSpacing.md),
        _AutopilotQuarantinePanel(summary: center.autopilotQuarantine),
        const SizedBox(height: AppSpacing.md),
        _TeamScorecardPanel(scorecard: center.teamScorecard),
        const SizedBox(height: AppSpacing.md),
        _MemoryGraphPanel(graph: center.memoryGraph),
        const SizedBox(height: AppSpacing.md),
        _ShadowModePanel(shadow: center.shadowMode),
        const SizedBox(height: AppSpacing.md),
        _ReviewQueueList(queue: center.reviewQueue),
        const SizedBox(height: AppSpacing.md),
        _EvidenceAuditPanel(audit: center.evidenceAudit),
        const SizedBox(height: AppSpacing.md),
        _EvidencePermissionPanel(permissions: center.evidencePermissions),
        const SizedBox(height: AppSpacing.md),
        _EvidenceRoomPanel(summary: center.evidenceRoom),
        const SizedBox(height: AppSpacing.md),
        _MeetingRecipePanel(policy: center.meetingRecipe),
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
        _AccuracyPanel(
          report: center.accuracyReport,
          extraction: center.extractionRecall,
        ),
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

class _CommandCenterActionsPanel extends StatelessWidget {
  final List<PromiseCommandCenterAction> actions;

  const _CommandCenterActionsPanel({required this.actions});

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
              '운영 액션',
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            if (actions.isEmpty)
              Text('사용 가능한 운영 액션이 없습니다.', style: theme.textTheme.bodySmall)
            else
              for (final action in actions.take(5)) ...[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      action.enabled
                          ? Icons.play_circle_outline_rounded
                          : Icons.pause_circle_outline_rounded,
                      size: 18,
                      color: action.enabled
                          ? Theme.of(context).colorScheme.primary
                          : Theme.of(context).disabledColor,
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            action.label,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          if (action.reason?.isNotEmpty ?? false)
                            Text(
                              action.reason!,
                              style: theme.textTheme.bodySmall,
                            ),
                        ],
                      ),
                    ),
                    Text(action.method, style: theme.textTheme.labelSmall),
                  ],
                ),
                const SizedBox(height: AppSpacing.xs),
              ],
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
                  icon: Icons.hub_outlined,
                  label: 'Alias ${insight.aliasGraphSize}',
                ),
                if (insight.ownerIdentityReviewCount > 0)
                  _MetricChip(
                    icon: Icons.manage_accounts_outlined,
                    label: 'Identity ${insight.ownerIdentityReviewCount}',
                  ),
                if (insight.hardNegativeCount > 0)
                  _MetricChip(
                    icon: Icons.rule_outlined,
                    label: 'Hard ${insight.hardNegativeCount}',
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
            if (insight.scopeBreakdown.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  for (final entry in insight.scopeBreakdown.entries.take(4))
                    _MetricChip(
                      icon: Icons.account_tree_outlined,
                      label: '${entry.key} ${entry.value}',
                    ),
                ],
              ),
            ],
            for (final recommendation
                in insight.scopeRecommendations.take(1)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(recommendation, style: theme.textTheme.bodySmall),
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

class _LearningTelemetryPanel extends StatelessWidget {
  final PromiseLearningTelemetryReport report;

  const _LearningTelemetryPanel({required this.report});

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
              'Production Learning Telemetry',
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
                  icon: Icons.insights_outlined,
                  label: 'Event ${report.eventCount}',
                ),
                _MetricChip(
                  icon: Icons.feedback_outlined,
                  label: 'Feedback ${report.feedbackEventCount}',
                ),
                _MetricChip(
                  icon: Icons.rule_folder_outlined,
                  label: '상태 ${report.statusSegments.length}',
                ),
                _MetricChip(
                  icon: Icons.translate_rounded,
                  label: '언어 ${report.localeSegments.length}',
                ),
              ],
            ),
            for (final segment in report.statusSegments.take(3)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                '${segment.value} · 오판 ${(segment.falsePositiveRate * 100).round()}% · 표본 ${segment.sampleCount}',
                style: theme.textTheme.bodySmall,
              ),
            ],
            for (final recommendation in report.recommendations.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(recommendation, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _LiveCoachPanel extends StatelessWidget {
  final PromiseLiveCoachSummary coach;

  const _LiveCoachPanel({required this.coach});

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
              'Live Promise Coach',
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
                  icon: Icons.fact_check_outlined,
                  label: '준비 ${coach.readinessScore}',
                ),
                _MetricChip(
                  icon: Icons.assistant_direction_outlined,
                  label: 'Prompt ${coach.promptCount}',
                ),
              ],
            ),
            for (final prompt in coach.prompts.take(3)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                '${prompt.label} · ${prompt.prompt}',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall,
              ),
            ],
            for (final note in coach.notes.take(1)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(note, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _AutopilotQuarantinePanel extends StatelessWidget {
  final PromiseAutopilotQuarantineSummary summary;

  const _AutopilotQuarantinePanel({required this.summary});

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
              'Autopilot Undo / Quarantine',
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
                  icon: Icons.undo_rounded,
                  label: '격리 ${summary.quarantinedCount}',
                ),
                _MetricChip(
                  icon: Icons.block_rounded,
                  label: '거절 ${summary.rejectedCount}',
                ),
                for (final entry in summary.affectedStatuses.entries.take(2))
                  _MetricChip(
                    icon: Icons.label_important_outline_rounded,
                    label: '${entry.key} ${entry.value}',
                  ),
              ],
            ),
            for (final note in summary.notes.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(note, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _TeamScorecardPanel extends StatelessWidget {
  final PromiseTeamScorecard scorecard;

  const _TeamScorecardPanel({required this.scorecard});

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
              'Team Scorecard',
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
                  icon: Icons.speed_rounded,
                  label: '위험 ${scorecard.riskScore}',
                ),
                _MetricChip(
                  icon: Icons.group_outlined,
                  label: '담당 ${scorecard.ownerCount}',
                ),
                _MetricChip(
                  icon: Icons.pending_actions_rounded,
                  label: '열림 ${scorecard.openCount}',
                ),
                _MetricChip(
                  icon: Icons.event_busy_rounded,
                  label: '초과 ${scorecard.overdueCount}',
                ),
              ],
            ),
            if (scorecard.weakestOwner?.isNotEmpty ?? false) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                '우선 확인: ${scorecard.weakestOwner}',
                style: theme.textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
            for (final recommendation in scorecard.recommendations.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(recommendation, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _MemoryGraphPanel extends StatelessWidget {
  final PromiseMemoryGraph graph;

  const _MemoryGraphPanel({required this.graph});

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
              'Promise Memory Graph',
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
                  icon: Icons.hub_outlined,
                  label: 'Node ${graph.nodeCount}',
                ),
                _MetricChip(
                  icon: Icons.linear_scale_rounded,
                  label: 'Edge ${graph.edgeCount}',
                ),
                _MetricChip(
                  icon: Icons.repeat_rounded,
                  label: '반복 ${graph.recurringSeriesCount}',
                ),
                _MetricChip(
                  icon: Icons.person_search_outlined,
                  label: 'Alias ${graph.ownerAliasCount}',
                ),
                _MetricChip(
                  icon: Icons.account_tree_outlined,
                  label: 'Identity ${graph.identityClusterCount}',
                ),
                if (graph.ownerAliasReviewCount > 0)
                  _MetricChip(
                    icon: Icons.manage_accounts_outlined,
                    label: 'Review ${graph.ownerAliasReviewCount}',
                  ),
              ],
            ),
            if (graph.nodes.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  for (final node in graph.nodes.take(4))
                    _MetricChip(
                      icon: Icons.circle_outlined,
                      label: '${node.kind}:${node.label}',
                    ),
                ],
              ),
            ],
            for (final edge in graph.edges.take(3)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                '${edge.source} -> ${edge.target} · ${edge.relationship}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall,
              ),
            ],
            for (final line in graph.narrative.take(3)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(line, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _ShadowModePanel extends StatelessWidget {
  final PromiseAutopilotShadowSummary shadow;

  const _ShadowModePanel({required this.shadow});

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
              'Autopilot Shadow Mode',
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
                  icon: Icons.visibility_outlined,
                  label: '후보 ${shadow.candidateCount}',
                ),
                _MetricChip(
                  icon: Icons.task_alt_rounded,
                  label: '적용 가능 ${shadow.wouldApplyCount}',
                ),
                _MetricChip(
                  icon: Icons.rule_rounded,
                  label: '미리보기 ${shadow.previewOnlyCount}',
                ),
                _MetricChip(
                  icon: Icons.lock_outline_rounded,
                  label: '보류 ${shadow.blockedByEvidenceCount}',
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(shadow.learningValue, style: theme.textTheme.bodySmall),
            for (final note in shadow.notes.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(note, style: theme.textTheme.bodySmall),
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

class _EvidencePermissionPanel extends StatelessWidget {
  final PromiseEvidencePermissionSummary permissions;

  const _EvidencePermissionPanel({required this.permissions});

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
              'Evidence Permission',
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
                  icon: permissions.exportAllowed
                      ? Icons.ios_share_rounded
                      : Icons.block_rounded,
                  label: permissions.exportAllowed ? 'Export 가능' : 'Export 제한',
                ),
                _MetricChip(
                  icon: Icons.privacy_tip_outlined,
                  label: permissions.redactionRequired ? 'Redaction' : 'Clean',
                ),
                _MetricChip(
                  icon: Icons.lock_outline_rounded,
                  label: '허용 ${permissions.allowedEvidenceCount}',
                ),
                _MetricChip(
                  icon: Icons.warning_amber_rounded,
                  label: '차단 ${permissions.blockedExportCount}',
                ),
              ],
            ),
            for (final note in permissions.policyNotes.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(note, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _EvidenceRoomPanel extends StatelessWidget {
  final PromiseEvidenceRoomSummary summary;

  const _EvidenceRoomPanel({required this.summary});

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
              'Privacy-Safe Evidence Room',
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
                  icon: Icons.ios_share_rounded,
                  label: '공유 ${summary.shareReadyCount}',
                ),
                _MetricChip(
                  icon: Icons.privacy_tip_outlined,
                  label: 'Redact ${summary.redactionRequiredCount}',
                ),
                _MetricChip(
                  icon: Icons.block_rounded,
                  label: '차단 ${summary.blockedCount}',
                ),
                _MetricChip(
                  icon: Icons.timer_outlined,
                  label: '${summary.defaultTtlHours}h',
                ),
              ],
            ),
            for (final note in summary.policyNotes.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(note, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _MeetingRecipePanel extends StatelessWidget {
  final PromiseMeetingRecipePolicy policy;

  const _MeetingRecipePanel({required this.policy});

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
              'Meeting Recipe',
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
                  icon: Icons.restaurant_menu_rounded,
                  label: policy.label,
                ),
                _MetricChip(
                  icon: policy.ownerRequired
                      ? Icons.person_search_outlined
                      : Icons.person_off_outlined,
                  label: policy.ownerRequired ? 'Owner 필수' : 'Owner 선택',
                ),
                _MetricChip(
                  icon: policy.dueDateRequired
                      ? Icons.event_available_outlined
                      : Icons.event_busy_outlined,
                  label: policy.dueDateRequired ? '기한 필수' : '기한 선택',
                ),
                _MetricChip(
                  icon: Icons.rule_rounded,
                  label: policy.defaultAutopilotMode,
                ),
              ],
            ),
            for (final template in policy.promptTemplates.take(2)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(template, style: theme.textTheme.bodySmall),
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
                  icon: Icons.timer_outlined,
                  label: 'SLA ${digest.slaDueTodayCount}',
                ),
                _MetricChip(
                  icon: digest.pushReady
                      ? Icons.notifications_active_outlined
                      : Icons.notifications_paused_outlined,
                  label: digest.pushReady ? 'Push 준비' : 'Push 대기',
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
                _MetricChip(
                  icon: oauth.productionReady
                      ? Icons.verified_user_outlined
                      : Icons.gpp_maybe_outlined,
                  label: oauth.productionReady ? '운영 준비' : '설정 필요',
                ),
                _MetricChip(
                  icon: oauth.oauthUxReady
                      ? Icons.phone_android_outlined
                      : Icons.phone_disabled_outlined,
                  label: oauth.oauthUxReady ? '앱 OAuth' : 'OAuth 대기',
                ),
                if (oauth.pkceRequired)
                  const _MetricChip(
                    icon: Icons.vpn_key_outlined,
                    label: 'PKCE',
                  ),
              ],
            ),
            if (oauth.missingSetup.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                '누락: ${oauth.missingSetup.join(', ')}',
                style: theme.textTheme.bodySmall,
              ),
            ],
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
            for (final step in oauth.verificationSteps.take(1)) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(step, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _AccuracyPanel extends StatelessWidget {
  final PromiseAccuracyReport report;
  final PromiseExtractionRecallReport extraction;

  const _AccuracyPanel({
    required this.report,
    required this.extraction,
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
                  icon: Icons.fact_check_outlined,
                  label:
                      'Recall ${(extraction.evaluation.recall * 100).round()}%',
                ),
                _MetricChip(
                  icon: Icons.playlist_add_check_circle_outlined,
                  label:
                      'FN ${extraction.evaluation.expectedCount - extraction.evaluation.matchedCount}',
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
