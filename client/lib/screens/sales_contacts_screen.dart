import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/models/sales_contact_brief.dart';
import 'package:voice_to_textnote/providers/sales_contact_brief_provider.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';
import 'package:voice_to_textnote/widgets/empty_state_widget.dart';

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
                  sliver: SliverList.separated(
                    itemCount: response.items.length,
                    separatorBuilder: (_, __) =>
                        const SizedBox(height: AppSpacing.sm),
                    itemBuilder: (context, index) {
                      final item = response.items[index];
                      return _SalesContactCard(
                        item: item,
                        onTap: () =>
                            context.push('/result/${item.sourceTaskId}'),
                      );
                    },
                  ),
                );
              },
            ),
          ],
        ),
      ),
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

  const _SalesContactCard({
    required this.item,
    required this.onTap,
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
                  const Icon(Icons.chevron_right_rounded),
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
