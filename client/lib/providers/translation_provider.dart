import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/translation.dart';
import 'package:voice_to_textnote/services/translation_api.dart';

class TranslationRequest {
  final String taskId;
  final String targetLanguage;
  final String? sourceLanguage;
  final String sourceType;

  const TranslationRequest({
    required this.taskId,
    required this.targetLanguage,
    this.sourceLanguage,
    this.sourceType = 'auto',
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is TranslationRequest &&
          runtimeType == other.runtimeType &&
          taskId == other.taskId &&
          targetLanguage == other.targetLanguage &&
          sourceLanguage == other.sourceLanguage &&
          sourceType == other.sourceType;

  @override
  int get hashCode => Object.hash(
        taskId,
        targetLanguage,
        sourceLanguage,
        sourceType,
      );
}

class TranslationNotifier extends AutoDisposeFamilyAsyncNotifier<
    TranslationResult, TranslationRequest> {
  late final TranslationApi _api;
  late final TranslationRequest _request;

  @override
  Future<TranslationResult> build(TranslationRequest arg) async {
    _request = arg;
    _api = ref.watch(translationApiProvider);
    try {
      return await _api.get(
        arg.taskId,
        targetLanguage: arg.targetLanguage,
        sourceType: arg.sourceType,
      );
    } on DioException catch (error) {
      if (error.response?.statusCode == 404) {
        return _api.create(
          arg.taskId,
          targetLanguage: arg.targetLanguage,
          sourceLanguage: arg.sourceLanguage,
          sourceType: arg.sourceType,
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
        targetLanguage: _request.targetLanguage,
        sourceLanguage: _request.sourceLanguage,
        sourceType: _request.sourceType,
        forceRefresh: true,
      ),
    );
  }
}

final translationProvider = AutoDisposeAsyncNotifierProviderFamily<
    TranslationNotifier,
    TranslationResult,
    TranslationRequest>(TranslationNotifier.new);
