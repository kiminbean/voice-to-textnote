import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/study_pack.dart';
import 'package:voice_to_textnote/services/study_pack_api.dart';

const _auxiliaryResultCacheTtl = Duration(minutes: 10);

class StudyPackRequest {
  final String taskId;
  final String mode;
  final String language;

  const StudyPackRequest({
    required this.taskId,
    this.mode = 'lecture',
    this.language = 'ko',
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is StudyPackRequest &&
          runtimeType == other.runtimeType &&
          taskId == other.taskId &&
          mode == other.mode &&
          language == other.language;

  @override
  int get hashCode => Object.hash(taskId, mode, language);
}

class StudyPackNotifier
    extends AutoDisposeFamilyAsyncNotifier<StudyPack, StudyPackRequest> {
  late final StudyPackApi _api;
  late final StudyPackRequest _request;

  @override
  Future<StudyPack> build(StudyPackRequest arg) async {
    final keepAliveLink = ref.keepAlive();
    final disposeTimer = Timer(_auxiliaryResultCacheTtl, keepAliveLink.close);
    ref.onDispose(disposeTimer.cancel);

    _request = arg;
    _api = ref.watch(studyPackApiProvider);
    try {
      return await _api.get(
        arg.taskId,
        mode: arg.mode,
        language: arg.language,
      );
    } on DioException catch (error) {
      if (error.response?.statusCode == 404) {
        return _api.create(
          arg.taskId,
          mode: arg.mode,
          language: arg.language,
        );
      }
      rethrow;
    }
  }

  Future<void> regenerate() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _api.create(
        _request.taskId,
        mode: _request.mode,
        language: _request.language,
        forceRefresh: true,
      ),
    );
  }
}

final studyPackProvider = AutoDisposeAsyncNotifierProviderFamily<
    StudyPackNotifier, StudyPack, StudyPackRequest>(StudyPackNotifier.new);
