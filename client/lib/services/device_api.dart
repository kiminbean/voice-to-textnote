import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/services/api_client.dart';

// @MX:ANCHOR: 디바이스 API 서비스
// @MX:REASON: FCM 토큰 등 디바이스 정보 등록
final deviceApiProvider = Provider<DeviceApi>((ref) {
  return DeviceApi(ref.watch(dioProvider));
});

class DeviceApi {
  final Dio _dio;

  DeviceApi(this._dio);

  /// FCM 토큰을 백엔드에 등록
  Future<void> registerDeviceToken(String token) async {
    await _dio.post(
      '/devices/register',
      data: {
        'fcm_token': token,
        'platform': 'flutter',
      },
    );
  }
}
