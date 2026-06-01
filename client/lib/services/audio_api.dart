// 오디오 스트리밍 API 서비스
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'api_client.dart';

final audioApiProvider = Provider<AudioApi>((ref) {
  final dio = ref.watch(dioProvider);
  return AudioApi(dio);
});

class AudioApi {
  final Dio _dio;

  AudioApi(this._dio);

  /// 오디오 스트리밍 URL 반환
  /// task_id에 해당하는 원본 오디오 파일의 스트리밍 URL을 생성한다.
  /// 파일이 만료된 경우 서버에서 404 응답.
  String getAudioUrl(String taskId) {
    return '${AppConfig.apiBaseUrl}/meetings/$taskId/audio';
  }

  /// 오디오 파일 존재 여부 확인 (HEAD 요청)
  Future<bool> isAudioAvailable(String taskId) async {
    try {
      await _dio.head('/meetings/$taskId/audio');
      return true;
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return false;
      rethrow;
    }
  }
}
