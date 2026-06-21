import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/study_pack.dart';
import 'package:voice_to_textnote/services/study_pack_api.dart';

class StudyPackNotifier
    extends AutoDisposeFamilyAsyncNotifier<StudyPack, String> {
  late final StudyPackApi _api;

  @override
  Future<StudyPack> build(String arg) async {
    _api = ref.watch(studyPackApiProvider);
    try {
      return await _api.get(arg);
    } on DioException catch (error) {
      if (error.response?.statusCode == 404) {
        return _api.create(arg);
      }
      rethrow;
    }
  }

  Future<void> regenerate() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _api.create(arg, forceRefresh: true),
    );
  }
}

final studyPackProvider = AutoDisposeAsyncNotifierProviderFamily<
    StudyPackNotifier, StudyPack, String>(StudyPackNotifier.new);
