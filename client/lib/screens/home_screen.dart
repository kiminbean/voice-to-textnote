// 홈 화면 - 미팅 목록 표시
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/widgets/meeting_card.dart';
import 'package:voice_to_textnote/widgets/offline_banner.dart';
import 'package:voice_to_textnote/widgets/shimmer_card.dart';
// @MX:NOTE: SPEC-TMPL-001에서 추가 - 양식 관리 화면 접근 버튼 포함

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meetings = ref.watch(meetingListProvider);
    final isLoading = meetings.isEmpty && _isInitialLoading(ref);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Voice to TextNote'),
        centerTitle: true,
        // 양식 관리 화면 이동 버튼 (SPEC-TMPL-001 REQ-TMPL-007)
        actions: [
          IconButton(
            icon: const Icon(Icons.folder_special_outlined),
            tooltip: '양식 관리',
            onPressed: () => context.push('/templates'),
          ),
        ],
      ),
      body: Column(
        children: [
          // 오프라인 배너 (서버 연결 불가 시 상단 표시)
          const OfflineBanner(),
          Expanded(
            child: isLoading
                // 로딩 중: shimmer 카드 표시
                ? _buildShimmerList()
                : meetings.isEmpty
                    ? const Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.mic_none, size: 64, color: Colors.grey),
                            SizedBox(height: 16),
                            Text(
                              '녹음된 미팅이 없습니다',
                              style:
                                  TextStyle(color: Colors.grey, fontSize: 16),
                            ),
                            SizedBox(height: 8),
                            Text(
                              '아래 버튼을 눌러 녹음을 시작하세요',
                              style:
                                  TextStyle(color: Colors.grey, fontSize: 14),
                            ),
                          ],
                        ),
                      )
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
                          );
                        },
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

  // 초기 로딩 여부 판단 (실제 로딩 상태 추가 시 교체)
  bool _isInitialLoading(WidgetRef ref) {
    // MVP에서는 항상 false (즉시 로딩된 목록 사용)
    return false;
  }

  // shimmer 로딩 리스트 (3개 카드)
  Widget _buildShimmerList() {
    return ListView.builder(
      itemCount: 3,
      itemBuilder: (_, __) => const ShimmerCard(),
    );
  }
}
