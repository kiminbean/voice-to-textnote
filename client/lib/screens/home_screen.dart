// 홈 화면 - 미팅 목록 표시
// @MX:NOTE: SPEC-TMPL-001에서 추가 - 양식 관리 화면 접근 버튼 포함
// @MX:NOTE: SPEC-SEARCH-001에서 추가 - 검색 화면 접근 버튼 포함
// @MX:NOTE: SPEC-TEAM-001에서 추가 - 팀 관리 화면 접근 버튼 포함
// @MX:NOTE: SPEC-HISTSYNC-001 - 서버 동기화, RefreshIndicator, 롱프레스 삭제 추가
// @MX:NOTE: SPEC-GUEST-001 - 게스트 모드 배너 추가
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/services/history_api.dart';
import 'package:voice_to_textnote/widgets/meeting_card.dart';
import 'package:voice_to_textnote/widgets/offline_banner.dart';
import 'package:voice_to_textnote/widgets/shimmer_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // AsyncNotifier로 변경되어 AsyncValue 처리 필요
    final meetingsAsync = ref.watch(meetingListProvider);
    // SPEC-GUEST-001: 게스트 상태 감시
    final authState = ref.watch(authStateProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Voice to TextNote'),
        centerTitle: true,
        // 모든 액션을 PopupMenuButton으로 통합 (UIX-008: 좁은 화면 오버플로우 방지)
        actions: [
          PopupMenuButton<String>(
            tooltip: '더보기',
            onSelected: (value) {
              switch (value) {
                case 'teams':
                  context.push('/teams');
                case 'search':
                  context.push('/search');
                case 'templates':
                  context.push('/templates');
                case 'logout':
                  _onLogout(context, ref);
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'teams',
                child: ListTile(
                  leading: Icon(Icons.groups),
                  title: Text('팀'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const PopupMenuItem(
                value: 'search',
                child: ListTile(
                  leading: Icon(Icons.search),
                  title: Text('검색'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const PopupMenuItem(
                value: 'templates',
                child: ListTile(
                  leading: Icon(Icons.folder_special_outlined),
                  title: Text('양식 관리'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
              const PopupMenuItem(
                value: 'logout',
                child: ListTile(
                  leading: Icon(Icons.logout),
                  title: Text('로그아웃'),
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          // 게스트 모드 배너 (SPEC-GUEST-001)
          if (authState.isGuest)
            Container(
              width: double.infinity,
              color: Colors.amber.shade50,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, size: 16, color: Colors.amber),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      '게스트 모드 — 데이터가 24시간 후 삭제됩니다',
                      style: TextStyle(fontSize: 13, color: Colors.black87),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      softWrap: true,
                    ),
                  ),
                  TextButton(
                    onPressed: () => context.push('/register'),
                    style: TextButton.styleFrom(
                      padding: EdgeInsets.zero,
                      minimumSize: const Size(0, 0),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    child: const Text(
                      '회원가입',
                      style: TextStyle(fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          // 오프라인 배너 (서버 연결 불가 시 상단 표시)
          const OfflineBanner(),
          Expanded(
            child: meetingsAsync.when(
              // SharedPreferences 로딩 중: shimmer 카드 표시 (REQ-HSYNC-006)
              loading: () => _buildShimmerList(),
              error: (_, __) => const Center(
                child: Text(
                  '미팅 목록을 불러올 수 없습니다',
                  style: TextStyle(color: Colors.grey),
                ),
              ),
              data: (meetings) => RefreshIndicator(
                // REQ-HSYNC-003: 당겨서 새로 고침 시 서버 동기화
                onRefresh: () => _onRefresh(context, ref),
                child: meetings.isEmpty
                    ? _buildEmptyState()
                    : ListView.builder(
                        itemCount: meetings.length,
                        itemBuilder: (context, index) {
                          final meeting = meetings[index];
                          return MeetingCard(
                            meeting: meeting,
                            onTap: () {
                              // 결과 화면으로 이동
                              context.push('/result/${meeting.id}');
                            },
                            // REQ-HSYNC-005: 롱프레스 삭제
                            onLongPress: () =>
                                _onLongPress(context, ref, meeting.id),
                          );
                        },
                      ),
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/recording'),
        tooltip: '새 녹음',
        child: const Icon(Icons.mic),
      ),
    );
  }

  // 로그아웃
  Future<void> _onLogout(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('로그아웃'),
        content: const Text('로그아웃하시겠습니까?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('로그아웃'),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      await ref.read(authStateProvider.notifier).logout();
    }
  }

  // REQ-HSYNC-003: 당겨서 새로 고침 처리
  // 오류 발생 시 SnackBar 표시 (REQ-HSYNC-007)
  Future<void> _onRefresh(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(meetingListProvider.notifier).refreshFromServer();
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('서버 동기화 실패. 로컬 데이터를 표시합니다.'),
            duration: Duration(seconds: 3),
          ),
        );
      }
    }
  }

  // REQ-HSYNC-005: 롱프레스 시 삭제 확인 다이얼로그 표시
  Future<void> _onLongPress(
    BuildContext context,
    WidgetRef ref,
    String meetingId,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('미팅 삭제'),
        content: const Text('이 미팅을 삭제하시겠습니까? 서버에서도 삭제됩니다.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      await _deleteMeeting(context, ref, meetingId);
    }
  }

  // 서버 + 로컬에서 미팅 삭제
  Future<void> _deleteMeeting(
    BuildContext context,
    WidgetRef ref,
    String meetingId,
  ) async {
    try {
      // 서버에서 삭제 시도 (실패해도 로컬은 삭제)
      final historyApi = ref.read(historyApiProvider);
      await historyApi.delete(meetingId);
    } catch (_) {
      // 서버 삭제 실패는 무시 (로컬만 삭제)
    } finally {
      await ref.read(meetingListProvider.notifier).removeMeeting(meetingId);
    }
  }

  // 빈 상태 위젯
  Widget _buildEmptyState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.mic_none, size: 64, color: Colors.grey),
          SizedBox(height: 16),
          Text(
            '녹음된 미팅이 없습니다',
            style: TextStyle(color: Colors.grey, fontSize: 16),
          ),
          SizedBox(height: 8),
          Text(
            '아래 버튼을 눌러 녹음을 시작하세요',
            style: TextStyle(color: Colors.grey, fontSize: 14),
          ),
        ],
      ),
    );
  }

  // shimmer 로딩 리스트 (3개 카드) (REQ-HSYNC-006)
  Widget _buildShimmerList() {
    return ListView.builder(
      itemCount: 3,
      itemBuilder: (_, __) => const ShimmerCard(),
    );
  }
}
