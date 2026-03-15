// 서버 상태 확인 API 서비스
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

// HealthApi 프로바이더
final healthApiProvider = Provider<HealthApi>((ref) {
  final dio = ref.watch(dioProvider);
  return HealthApi(dio);
});

class HealthApi {
  final Dio _dio;

  HealthApi(this._dio);

  // 서버 헬스체크 - 정상이면 true, 오류면 false 반환
  Future<bool> check() async {
    try {
      final response = await _dio.get('/health');
      return response.statusCode == 200;
    } catch (_) {
      // 연결 오류 또는 서버 오류 시 false 반환
      return false;
    }
  }
}
