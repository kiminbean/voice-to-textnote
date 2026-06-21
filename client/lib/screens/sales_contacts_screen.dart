import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import 'package:voice_to_textnote/models/sales_contact_brief.dart';
import 'package:voice_to_textnote/providers/sales_contact_brief_provider.dart';
import 'package:voice_to_textnote/services/sales_contact_brief_api.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';

final salesContactCsvShareProvider =
    Provider<Future<void> Function(String)>((ref) {
  return (csv) => Share.share(csv, subject: 'sales-contacts.csv');
});

class SalesContactsScreen extends ConsumerStatefulWidget {
  const SalesContactsScreen({super.key});

  @override
  ConsumerState<SalesContactsScreen> createState() =>
      _SalesContactsScreenState();
}

class _SalesContactsScreenState extends ConsumerState<SalesContactsScreen> {
  final TextEditingController _controller = TextEditingController();
  Timer? _debounce;
  String _query = '';
  _SalesStageFilter _stageFilter = _SalesStageFilter.all;

  @override
  void initState() {
    super.initState();
    _controller.addListener(_onQueryChanged);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.removeListener(_onQueryChanged);
    _controller.dispose();
    super.dispose();
  }

  void _onQueryChanged() {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 250), () {
      if (!mounted) return;
      setState(() {
        _query = _controller.text.trim();
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final request = SalesContactListRequest(query: _query);
    final contactsAsync = ref.watch(salesContactListProvider(request));

    return Scaffold(
      appBar: AppBar(
        leading: BackButton(onPressed: () => context.pop()),
        title: const Text('영업 고객'),
        actions: [
          IconButton(
            tooltip: 'CRM CSV 공유',
            icon: const Icon(Icons.ios_share_rounded),
            onPressed: () => _shareCrmCsv(context, ref),
          ),
          IconButton(
            tooltip: '새로고침',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(salesContactListProvider(request)),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.refresh(salesContactListProvider(request)),
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.lg,
                AppSpacing.md,
                AppSpacing.lg,
                AppSpacing.sm,
              ),
              sliver: SliverToBoxAdapter(
                  child: _SearchField(controller: _controller)),
            ),
            contactsAsync.when(
              loading: () => const SliverFillRemaining(
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (_, __) => SliverFillRemaining(
                hasScrollBody: false,
                child: EmptyStateWidget(
                  icon: Icons.cloud_off_rounded,
                  title: '영업 고객 목록을 불러올 수 없습니다',
                  subtitle: '잠시 후 다시 시도해주세요',
                  actionLabel: '다시 시도',
                  onAction: () =>
                      ref.invalidate(salesContactListProvider(request)),
                ),
              ),
              data: (response) {
                final visibleItems = response.items
                    .where((item) => _stageFilter.matches(item))
                    .toList();
                if (response.items.isEmpty) {
                  return SliverFillRemaining(
                    hasScrollBody: false,
                    child: EmptyStateWidget(
                      icon: Icons.contact_page_outlined,
                      title: _query.isEmpty ? '아직 영업 브리프가 없습니다' : '검색 결과가 없습니다',
                      subtitle: _query.isEmpty
                          ? '회의 결과 화면의 영업 탭에서 고객 브리프를 생성하면 여기에 모입니다'
                          : '회사명, 고객명, 니즈로 다시 검색해보세요',
                    ),
                  );
                }

                return SliverPadding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.lg,
                    AppSpacing.sm,
                    AppSpacing.lg,
                    AppSpacing.xxxl,
                  ),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate(
                      [
                        _LifecycleFilterBar(
                          selected: _stageFilter,
                          items: response.items,
                          onSelected: (filter) =>
                              setState(() => _stageFilter = filter),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        if (visibleItems.isEmpty)
                          EmptyStateWidget(
                            icon: Icons.filter_alt_off_rounded,
                            title: '${_stageFilter.label} 고객이 없습니다',
                            subtitle: '다른 단계 필터를 선택해보세요',
                          )
                        else ...[
                          for (final item in visibleItems) ...[
                            _SalesContactCard(
                              item: item,
                              onTap: () =>
                                  context.push('/result/${item.sourceTaskId}'),
                              onEditCrm: () => _showCrmEditor(
                                context,
                                ref,
                                request,
                                item,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.sm),
                          ],
                        ],
                      ],
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _showCrmEditor(
    BuildContext context,
    WidgetRef ref,
    SalesContactListRequest request,
    SalesContactListItem item,
  ) async {
    var status = item.crmStatus;
    var note = item.crmNote;
    final messenger = ScaffoldMessenger.of(context);
    final api = ref.read(salesContactBriefApiProvider);
    try {
      final saved = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text('${_contactTitle(item.contact)} CRM 메모'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                initialValue: status,
                decoration: const InputDecoration(
                  labelText: '상태',
                  hintText: 'open, follow_up, won, lost',
                ),
                onChanged: (value) => status = value,
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: AppSpacing.sm),
              TextFormField(
                initialValue: note,
                decoration: const InputDecoration(
                  labelText: '메모',
                  hintText: '다음 연락 시점, 견적 조건, 의사결정자 등',
                ),
                onChanged: (value) => note = value,
                minLines: 3,
                maxLines: 5,
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('취소'),
            ),
            FilledButton.icon(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              icon: const Icon(Icons.save_outlined),
              label: const Text('저장'),
            ),
          ],
        ),
      );
      if (saved != true) return;

      await api.updateContactCrm(
        artifactTaskId: item.artifactTaskId,
        status: status.trim().isEmpty ? 'open' : status.trim(),
        note: note.trim(),
      );
      ref.invalidate(salesContactListProvider(request));
      messenger.showSnackBar(
        const SnackBar(content: Text('CRM 메모를 저장했습니다')),
      );
    } catch (_) {
      messenger.showSnackBar(
        const SnackBar(content: Text('CRM 메모를 저장할 수 없습니다')),
      );
    }
  }

  Future<void> _shareCrmCsv(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final api = ref.read(salesContactBriefApiProvider);
    final shareCsv = ref.read(salesContactCsvShareProvider);
    try {
      final csv = await api.exportContactsCsv(query: _query);
      if (csv.trim().isEmpty) {
        messenger.showSnackBar(
          const SnackBar(content: Text('내보낼 영업 고객이 없습니다')),
        );
        return;
      }
      await shareCsv(csv);
    } catch (_) {
      messenger.showSnackBar(
        const SnackBar(content: Text('CRM CSV를 내보낼 수 없습니다')),
      );
    }
  }
}

enum _SalesStageFilter {
  all('전체'),
  active('진행 중'),
  demo('데모/제안'),
  urgent('긴급'),
  closed('종료');

  final String label;

  const _SalesStageFilter(this.label);

  bool matches(SalesContactListItem item) {
    final stage = item.deal.stage.trim();
    final urgency = item.deal.urgency.trim();
    return switch (this) {
      _SalesStageFilter.all => true,
      _SalesStageFilter.active =>
        stage != 'closed' && stage != 'lost' && stage != 'unknown',
      _SalesStageFilter.demo =>
        stage == 'demo_requested' || stage == 'proposal',
      _SalesStageFilter.urgent => urgency == 'high',
      _SalesStageFilter.closed => stage == 'closed' || stage == 'lost',
    };
  }
}

class _LifecycleFilterBar extends StatelessWidget {
  final _SalesStageFilter selected;
  final List<SalesContactListItem> items;
  final ValueChanged<_SalesStageFilter> onSelected;

  const _LifecycleFilterBar({
    required this.selected,
    required this.items,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final openCount = items.where(_SalesStageFilter.active.matches).length;
    final urgentCount = items.where(_SalesStageFilter.urgent.matches).length;
    final closedCount = items.where(_SalesStageFilter.closed.matches).length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '후속관리 단계',
          style: textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: AppSpacing.xs),
        Text(
          '진행 중 $openCount · 긴급 $urgentCount · 종료 $closedCount',
          style: textTheme.bodySmall?.copyWith(color: colors.onSurfaceVariant),
        ),
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: [
            for (final filter in _SalesStageFilter.values)
              ChoiceChip(
                label: Text(filter.label),
                selected: selected == filter,
                onSelected: (_) => onSelected(filter),
              ),
          ],
        ),
      ],
    );
  }
}

class _SearchField extends StatelessWidget {
  final TextEditingController controller;

  const _SearchField({required this.controller});

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      decoration: InputDecoration(
        prefixIcon: const Icon(Icons.search_rounded),
        hintText: '고객명, 회사명, 니즈 검색',
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      textInputAction: TextInputAction.search,
    );
  }
}

class _SalesContactCard extends StatelessWidget {
  final SalesContactListItem item;
  final VoidCallback onTap;
  final VoidCallback onEditCrm;

  const _SalesContactCard({
    required this.item,
    required this.onTap,
    required this.onEditCrm,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final title = _contactTitle(item.contact);
    final subtitle = [
      item.contact.role,
      _dealStageLabel(item.deal.stage),
      _urgencyLabel(item.deal.urgency),
    ].whereType<String>().where((value) => value.isNotEmpty).join(' · ');

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    backgroundColor: colors.primaryContainer,
                    foregroundColor: colors.onPrimaryContainer,
                    child: const Icon(Icons.business_center_rounded),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        if (subtitle.isNotEmpty)
                          Text(
                            subtitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: textTheme.bodySmall?.copyWith(
                              color: colors.onSurfaceVariant,
                            ),
                          ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'CRM 메모 편집',
                    icon: const Icon(Icons.edit_note_rounded),
                    onPressed: onEditCrm,
                  ),
                  const Icon(Icons.chevron_right_rounded),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: AppSpacing.xs,
                runSpacing: AppSpacing.xs,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Chip(
                    visualDensity: VisualDensity.compact,
                    avatar: const Icon(Icons.edit_calendar_outlined, size: 18),
                    label: Text(_crmStatusLabel(item.crmStatus)),
                  ),
                  if (item.crmNote.trim().isNotEmpty)
                    Text(
                      item.crmNote,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodySmall?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                ],
              ),
              if (item.customerNeeds.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                Wrap(
                  spacing: AppSpacing.xs,
                  runSpacing: AppSpacing.xs,
                  children: item.customerNeeds
                      .take(3)
                      .map((need) => Chip(
                            visualDensity: VisualDensity.compact,
                            label: Text(need),
                          ))
                      .toList(),
                ),
              ],
              if (item.nextSteps.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      Icons.flag_rounded,
                      size: 18,
                      color: colors.primary,
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(
                      child: Text(
                        item.nextSteps.first.task,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: textTheme.bodyMedium,
                      ),
                    ),
                  ],
                ),
              ],
              if (item.followUpMessage.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  item.followUpMessage,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: textTheme.bodySmall?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

String _contactTitle(SalesContactIdentity contact) {
  final name = contact.name?.trim();
  final company = contact.company?.trim();
  if (company != null &&
      company.isNotEmpty &&
      name != null &&
      name.isNotEmpty) {
    return '$company · $name';
  }
  if (company != null && company.isNotEmpty) return company;
  if (name != null && name.isNotEmpty) return name;
  return '미확인 고객';
}

String _dealStageLabel(String stage) {
  return switch (stage) {
    'lead' => '리드',
    'qualified' => '검증됨',
    'demo_requested' => '데모 요청',
    'proposal' => '제안',
    'negotiation' => '협상',
    'closed' => '종료',
    _ => '단계 미정',
  };
}

String _urgencyLabel(String urgency) {
  return switch (urgency) {
    'high' => '긴급',
    'medium' => '보통',
    'low' => '낮음',
    _ => '',
  };
}

String _crmStatusLabel(String status) {
  return switch (status) {
    'follow_up' => '후속 예정',
    'won' => '성사',
    'lost' => '실패',
    'paused' => '보류',
    'open' => '열림',
    _ => status.isEmpty ? '열림' : status,
  };
}
