// 결과 화면 - 회의록, AI 요약, 액션 아이템 표시
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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
class _TranscriptTab extends StatelessWidget {
  final String meetingId;

  const _TranscriptTab({required this.meetingId});

  @override
  Widget build(BuildContext context) {
    // MVP: 샘플 데이터로 표시 (실제 구현 시 API 연동)
    final segments = [
      ('스피커 1', '안녕하세요. 오늘 회의를 시작하겠습니다.', const Duration(seconds: 0), 0),
      ('스피커 2', '네, 먼저 지난 주 진행 상황을 공유해 주세요.', const Duration(seconds: 10), 1),
      ('스피커 1', '지난 주에는 사용자 인터페이스 개발을 완료했습니다.', const Duration(seconds: 20), 0),
    ];

    return ListView.builder(
      itemCount: segments.length,
      itemBuilder: (context, index) {
        final (name, text, time, speakerIdx) = segments[index];
        return SpeakerSegment(
          speakerName: name,
          text: text,
          startTime: time,
          speakerIndex: speakerIdx,
        );
      },
    );
  }
}

// AI 요약 탭
class _SummaryTab extends StatelessWidget {
  final String meetingId;

  const _SummaryTab({required this.meetingId});

  @override
  Widget build(BuildContext context) {
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
              const Text(
                '회의에서 UI 개발 완료 및 다음 단계 논의가 이루어졌습니다.',
                style: TextStyle(height: 1.6),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// 액션 아이템 탭
class _ActionItemsTab extends StatefulWidget {
  final String meetingId;

  const _ActionItemsTab({required this.meetingId});

  @override
  State<_ActionItemsTab> createState() => _ActionItemsTabState();
}

class _ActionItemsTabState extends State<_ActionItemsTab> {
  // MVP: 샘플 액션 아이템
  final List<(String, bool)> _items = [
    ('UI 컴포넌트 리뷰 진행', false),
    ('API 연동 테스트', false),
    ('다음 주 배포 계획 수립', false),
  ];

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _items.length,
      itemBuilder: (context, index) {
        final (text, done) = _items[index];
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
              _items[index] = (text, value ?? false);
            });
          },
        );
      },
    );
  }
}
