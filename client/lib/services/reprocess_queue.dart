// SPEC-MOBILE-002: 오프라인 전사 결과 재처리 큐
//
// 오프라인에서 로컬 STT로 처리된 결과를 네트워크 복구 시
// 서버로 재전송하여 고품질 전사로 교체한다.
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

final reprocessQueueProvider = Provider<ReprocessQueue>((ref) {
  return ReprocessQueue();
});

class QueuedItem {
  final String taskId;
  final String audioFilePath;
  final String localText;
  final DateTime createdAt;
  bool isProcessing;

  QueuedItem({
    required this.taskId,
    required this.audioFilePath,
    required this.localText,
    required this.createdAt,
    this.isProcessing = false,
  });

  Map<String, dynamic> toJson() => {
        'task_id': taskId,
        'audio_file_path': audioFilePath,
        'local_text': localText,
        'created_at': createdAt.toIso8601String(),
      };

  factory QueuedItem.fromJson(Map<String, dynamic> json) {
    return QueuedItem(
      taskId: json['task_id'] as String,
      audioFilePath: json['audio_file_path'] as String,
      localText: json['local_text'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

class ReprocessQueue {
  static const _kPrefsQueue = 'reprocess_queue_items';

  List<QueuedItem> _items = [];

  List<QueuedItem> get items => List.unmodifiable(_items);
  int get length => _items.length;
  bool get isEmpty => _items.isEmpty;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_kPrefsQueue);
    if (raw == null) {
      _items = [];
      return;
    }
    try {
      final list = jsonDecode(raw) as List;
      _items = list
          .map((e) => QueuedItem.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      _items = [];
    }
  }

  Future<void> enqueue({
    required String taskId,
    required String audioFilePath,
    required String localText,
  }) async {
    final exists = _items.any((e) => e.taskId == taskId);
    if (exists) return;

    _items.add(QueuedItem(
      taskId: taskId,
      audioFilePath: audioFilePath,
      localText: localText,
      createdAt: DateTime.now(),
    ));
    await _persist();
  }

  Future<void> remove(String taskId) async {
    _items.removeWhere((e) => e.taskId == taskId);
    await _persist();
  }

  Future<void> markProcessing(String taskId) async {
    final item = _items.where((e) => e.taskId == taskId).firstOrNull;
    if (item != null) {
      item.isProcessing = true;
    }
  }

  QueuedItem? peek() {
    return _items.where((e) => !e.isProcessing).firstOrNull;
  }

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = jsonEncode(_items.map((e) => e.toJson()).toList());
    await prefs.setString(_kPrefsQueue, encoded);
  }

  Future<void> clear() async {
    _items = [];
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kPrefsQueue);
  }
}

