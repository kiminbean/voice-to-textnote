// SPEC-TONE-001: 톤 분석 API 클라이언트 (REQ-TONE-012, REQ-TONE-013)
// @MX:SPEC: SPEC-TONE-001
// 패턴 매칭: sentiment_api.dart (dioProvider 주입, Provider 선언 방식)
//
// @MX:WARN: 모든 오류는 예외로 throw - null/빈 반환 절대 금지 (REQ-TONE-013)
// @MX:REASON: SPEC-SENTIMENT-001의 SizedBox.shrink() silent failure 반복 방지
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/models/tone_model.dart';
import 'package:voice_to_textnote/services/api_client.dart';

// SPEC-TONE-001: toneApiProvider - sentimentApiProvider 패턴 매칭
final toneApiProvider = Provider<ToneApi>((ref) {
  final dio = ref.watch(dioProvider);
  return ToneApi(dio);
});

/// 톤 분석 API 공통 예외 (모든 톤 API 오류의 부모)
class ToneApiException implements Exception {
  final String message;
  final int? statusCode;

  const ToneApiException(this.message, {this.statusCode});

  @override
  String toString() =>
      'ToneApiException($statusCode): $message';
}

/// 404 - 톤 분석 결과 없음
class ToneNotFoundException extends ToneApiException {
  ToneNotFoundException([String? taskId])
      : super(
          taskId != null
              ? '톤 분석 결과를 찾을 수 없습니다 (taskId: $taskId)'
              : '톤 분석 결과를 찾을 수 없습니다',
          statusCode: 404,
        );
}

/// 503 - 톤 분석 기능 비활성화 (tone_model 미로드)
class ToneDisabledException extends ToneApiException {
  const ToneDisabledException()
      : super('톤 분석 기능이 비활성화되어 있습니다', statusCode: 503);
}

/// 톤 분석 API 클라이언트
///
/// GET /api/v1/tone/{task_id} → ToneResponse
/// GET /api/v1/tone/meeting/{meeting_id} → ToneResponse
///
/// 404 → ToneNotFoundException
/// 503 → ToneDisabledException (기능 비활성화)
/// 기타 → ToneApiException
class ToneApi {
  final Dio _dio;

  ToneApi(this._dio);

  /// task_id 기반 톤 분석 결과 조회
  ///
  /// REQ-TONE-013: 오류 발생 시 반드시 예외 throw. null/빈 반환 없음.
  Future<ToneResponse> getToneResult(String taskId) async {
    try {
      final response = await _dio.get('/tone/$taskId');
      return ToneResponse.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      // 모든 경로가 throw하므로 catch 블록 이후로 제어권이 넘어가지 않음
      final statusCode = e.response?.statusCode;
      if (statusCode == 404) throw ToneNotFoundException(taskId);
      if (statusCode == 503) throw const ToneDisabledException();
      throw ToneApiException(
        e.message ?? '톤 분석 API 요청 실패',
        statusCode: statusCode,
      );
    }
  }

  /// meeting_id 기반 톤 분석 결과 조회
  ///
  /// REQ-TONE-013: 오류 발생 시 반드시 예외 throw. null/빈 반환 없음.
  Future<ToneResponse> getToneByMeeting(String meetingId) async {
    try {
      final response = await _dio.get('/tone/meeting/$meetingId');
      return ToneResponse.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      final statusCode = e.response?.statusCode;
      if (statusCode == 404) throw ToneNotFoundException(meetingId);
      if (statusCode == 503) throw const ToneDisabledException();
      throw ToneApiException(
        e.message ?? '톤 분석 API 요청 실패',
        statusCode: statusCode,
      );
    }
  }
}
