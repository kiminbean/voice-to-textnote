// 화자 프로필 CRUD API 서비스 — SPEC-SPEAKER-001
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/speaker_profile.dart';
import 'api_client.dart';

final speakerApiProvider = Provider<SpeakerApi>((ref) {
  final dio = ref.watch(dioProvider);
  return SpeakerApi(dio);
});

class SpeakerApi {
  final Dio _dio;

  SpeakerApi(this._dio);

  /// 화자 프로필 목록 조회
  /// taskId: 특정 회의의 프로필 + 전역 프로필 반환
  Future<List<SpeakerProfile>> list({String? taskId}) async {
    final params = <String, dynamic>{};
    if (taskId != null) params['task_id'] = taskId;

    final res = await _dio.get('/speakers', queryParameters: params);
    final items = res.data['items'] as List<dynamic>;
    return items.map((e) => SpeakerProfile.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// 화자 프로필 생성
  Future<SpeakerProfile> create(SpeakerProfileCreate payload) async {
    final res = await _dio.post('/speakers', data: payload.toJson());
    return SpeakerProfile.fromJson(res.data as Map<String, dynamic>);
  }

  /// 화자 프로필 수정
  Future<SpeakerProfile> update(String id, SpeakerProfileUpdate payload) async {
    final res = await _dio.patch('/speakers/$id', data: payload.toJson());
    return SpeakerProfile.fromJson(res.data as Map<String, dynamic>);
  }

  /// 화자 프로필 삭제
  Future<void> delete(String id) async {
    await _dio.delete('/speakers/$id');
  }
}
