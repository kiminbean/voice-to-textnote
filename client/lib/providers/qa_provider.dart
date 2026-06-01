// 회의 Q&A 상태 관리 — SPEC-QA-001
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/qa_api.dart';

/// 채팅 메시지
class ChatMessage {
  final String text;
  final bool isUser;
  final List<QASource> sources;

  const ChatMessage({
    required this.text,
    required this.isUser,
    this.sources = const [],
  });
}

/// Q&A 상태
class QAState {
  final List<ChatMessage> messages;
  final bool isLoading;
  final String? threadId;
  final String? error;

  const QAState({
    this.messages = const [],
    this.isLoading = false,
    this.threadId,
    this.error,
  });

  QAState copyWith({
    List<ChatMessage>? messages,
    bool? isLoading,
    String? threadId,
    String? error,
  }) =>
      QAState(
        messages: messages ?? this.messages,
        isLoading: isLoading ?? this.isLoading,
        threadId: threadId ?? this.threadId,
        error: error,
      );
}

class QANotifier extends StateNotifier<QAState> {
  final QAApi _api;
  final String _taskId;

  QANotifier(this._api, this._taskId) : super(const QAState());

  Future<void> ask(String question) async {
    if (question.trim().isEmpty || state.isLoading) return;

    // 사용자 메시지 추가
    final updated = [
      ...state.messages,
      ChatMessage(text: question, isUser: true),
    ];
    state = state.copyWith(messages: updated, isLoading: true, error: null);

    try {
      final res = await _api.ask(
        taskId: _taskId,
        question: question,
        threadId: state.threadId,
      );

      state = state.copyWith(
        messages: [
          ...state.messages,
          ChatMessage(text: res.answer, isUser: false, sources: res.sources),
        ],
        threadId: res.threadId,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(
        messages: [
          ...state.messages,
          ChatMessage(text: '답변을 생성할 수 없습니다: $e', isUser: false),
        ],
        isLoading: false,
        error: e.toString(),
      );
    }
  }
}

/// Q&A 프로바이더 (task_id별로 독립 상태)
final qaProvider =
    StateNotifierProvider.family<QANotifier, QAState, String>((ref, taskId) {
  final api = ref.watch(qaApiProvider);
  return QANotifier(api, taskId);
});
