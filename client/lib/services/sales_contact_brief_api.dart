import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/sales_contact_brief.dart';

import 'api_client.dart';

final salesContactBriefApiProvider = Provider<SalesContactBriefApi>((ref) {
  final dio = ref.watch(dioProvider);
  return SalesContactBriefApi(dio);
});

class SalesContactBriefApi {
  final Dio _dio;

  SalesContactBriefApi(this._dio);

  Future<SalesContactBrief> create(
    String minutesTaskId, {
    String language = 'ko',
    bool forceRefresh = false,
  }) async {
    final response = await _dio.post(
      '/minutes/$minutesTaskId/sales-contact-brief',
      data: {
        'language': language,
        'force_refresh': forceRefresh,
      },
    );
    return SalesContactBrief.fromJson(response.data as Map<String, dynamic>);
  }

  Future<SalesContactBrief> get(String minutesTaskId) async {
    final response = await _dio.get(
      '/minutes/$minutesTaskId/sales-contact-brief',
    );
    return SalesContactBrief.fromJson(response.data as Map<String, dynamic>);
  }
}
