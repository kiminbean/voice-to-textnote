import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/promise_radar.dart';

import 'api_client.dart';

final promiseRadarApiProvider = Provider<PromiseRadarApi>((ref) {
  final dio = ref.watch(dioProvider);
  return PromiseRadarApi(dio);
});

class PromiseRadarApi {
  final Dio _dio;

  PromiseRadarApi(this._dio);

  Future<PromiseRadarResult> getRadar(String taskId, {int limit = 30}) async {
    final response = await _dio.get(
      '/promise-radar/$taskId',
      queryParameters: {'limit': limit},
    );
    return PromiseRadarResult.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<PromiseLedgerEntry>> listLedger({
    List<String>? statuses,
    int limit = 50,
  }) async {
    final response = await _dio.get(
      '/promise-radar/ledger',
      queryParameters: {
        if (statuses != null && statuses.isNotEmpty) 'status': statuses,
        'limit': limit,
      },
    );
    return (response.data as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(PromiseLedgerEntry.fromJson)
        .toList();
  }

  Future<PromiseNextMeetingBriefing> getNextMeetingBriefing({
    int limit = 30,
  }) async {
    final response = await _dio.get(
      '/promise-radar/briefing/next',
      queryParameters: {'limit': limit},
    );
    return PromiseNextMeetingBriefing.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseLedgerEntry> updateLedgerEntry(
    String entryId,
    PromiseLedgerUpdateRequest request,
  ) async {
    final response = await _dio.patch(
      '/promise-radar/ledger/$entryId',
      data: request.toJson(),
    );
    return PromiseLedgerEntry.fromJson(response.data as Map<String, dynamic>);
  }

  Future<PromiseReminderCandidate> createCalendarCandidate(
    String entryId,
  ) async {
    final response = await _dio.post('/promise-radar/ledger/$entryId/calendar');
    return PromiseReminderCandidate.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<PromiseTaskLinkResponse> createActionItem(String entryId) async {
    final response =
        await _dio.post('/promise-radar/ledger/$entryId/action-item');
    return PromiseTaskLinkResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }
}
