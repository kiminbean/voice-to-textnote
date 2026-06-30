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
}
