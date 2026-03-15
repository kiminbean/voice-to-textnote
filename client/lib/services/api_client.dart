// API 클라이언트 설정 및 Dio 인스턴스 관리
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';

// Dio 싱글톤 프로바이더
final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: AppConfig.apiTimeout,
    receiveTimeout: AppConfig.apiTimeout,
    sendTimeout: AppConfig.apiTimeout,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  ));

  // 에러 처리 인터셉터 추가
  dio.interceptors.add(InterceptorsWrapper(
    onError: (DioException error, ErrorInterceptorHandler handler) {
      // 에러 로깅
      final statusCode = error.response?.statusCode;
      final message = error.message;
      // ignore: avoid_print
      print('[API 오류] 상태코드: $statusCode, 메시지: $message');
      handler.next(error);
    },
  ));

  return dio;
});
