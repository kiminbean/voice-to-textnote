// 회의록 생성 API 서비스
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';

// MinutesApi 프로바이더
final minutesApiProvider = Provider<MinutesApi>((ref) {
  final dio = ref.watch(dioProvider);
  return MinutesApi(dio);
});

class MinutesApi {
  final Dio _dio;

  MinutesApi(this._dio);

  // 화자 분리 태스크 ID로 회의록 생성
  //
  // [sttTaskId]가 제공되면 병렬 모드로 매칭됨. STT와 DIA를 동시 시작한 경우
  // DIA 결과가 matched=False일 수 있어 minutes_task가 직접 매칭한다.
  Future<Map<String, dynamic>> create(
    String diaTaskId, {
    String? sttTaskId,
  }) async {
    final data = <String, dynamic>{'diarization_task_id': diaTaskId};
    if (sttTaskId != null) {
      data['stt_task_id'] = sttTaskId;
    }
    final response = await _dio.post('/minutes', data: data);
    return response.data as Map<String, dynamic>;
  }

  // 태스크 상태 조회
  Future<Map<String, dynamic>> getStatus(String taskId) async {
    final response = await _dio.get('/minutes/$taskId/status');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 결과 조회
  Future<Map<String, dynamic>> getResult(String taskId) async {
    final response = await _dio.get('/minutes/$taskId');
    return response.data as Map<String, dynamic>;
  }

  // 태스크 삭제
  Future<void> delete(String taskId) async {
    await _dio.delete('/minutes/$taskId');
  }
}
