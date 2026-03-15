// 홈 화면 - 미팅 목록 표시
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/meeting_list_provider.dart';
import 'package:voice_to_textnote/widgets/meeting_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meetings = ref.watch(meetingListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Voice to TextNote'),
        centerTitle: true,
      ),
      body: meetings.isEmpty
          ? const Center(
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
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/recording'),
        tooltip: '새 녹음',
        child: const Icon(Icons.mic),
      ),
    );
  }
}
