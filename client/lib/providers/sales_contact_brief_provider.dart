import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/sales_contact_brief.dart';
import 'package:voice_to_textnote/services/sales_contact_brief_api.dart';

const _auxiliaryResultCacheTtl = Duration(minutes: 10);

class SalesContactBriefRequest {
  final String taskId;
  final String language;

  const SalesContactBriefRequest({
    required this.taskId,
    this.language = 'ko',
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SalesContactBriefRequest &&
          runtimeType == other.runtimeType &&
          taskId == other.taskId &&
          language == other.language;

  @override
  int get hashCode => Object.hash(taskId, language);
}

class SalesContactBriefNotifier extends AutoDisposeFamilyAsyncNotifier<
    SalesContactBrief, SalesContactBriefRequest> {
  late final SalesContactBriefApi _api;
  late final SalesContactBriefRequest _request;

  @override
  Future<SalesContactBrief> build(SalesContactBriefRequest arg) async {
    final keepAliveLink = ref.keepAlive();
    final disposeTimer = Timer(_auxiliaryResultCacheTtl, keepAliveLink.close);
    ref.onDispose(disposeTimer.cancel);

    _request = arg;
    _api = ref.watch(salesContactBriefApiProvider);
    try {
      return await _api.get(arg.taskId);
    } on DioException catch (error) {
      if (error.response?.statusCode == 404) {
        return _api.create(arg.taskId, language: arg.language);
      }
      rethrow;
    }
  }

  Future<void> regenerate() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _api.create(
        _request.taskId,
        language: _request.language,
        forceRefresh: true,
      ),
    );
  }
}

final salesContactBriefProvider = AutoDisposeAsyncNotifierProviderFamily<
    SalesContactBriefNotifier,
    SalesContactBrief,
    SalesContactBriefRequest>(SalesContactBriefNotifier.new);

class SalesContactListRequest {
  final String query;
  final int page;
  final int pageSize;

  const SalesContactListRequest({
    this.query = '',
    this.page = 1,
    this.pageSize = 20,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SalesContactListRequest &&
          runtimeType == other.runtimeType &&
          query == other.query &&
          page == other.page &&
          pageSize == other.pageSize;

  @override
  int get hashCode => Object.hash(query, page, pageSize);
}

final salesContactListProvider = FutureProvider.autoDispose
    .family<SalesContactListResponse, SalesContactListRequest>(
        (ref, request) async {
  final api = ref.watch(salesContactBriefApiProvider);
  return api.listContacts(
    query: request.query,
    page: request.page,
    pageSize: request.pageSize,
  );
});
