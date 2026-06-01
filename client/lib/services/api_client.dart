// API 클라이언트 설정 및 Dio 인스턴스 관리
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'package:voice_to_textnote/services/auth_service.dart';

// @MX:ANCHOR: 앱 전체 HTTP 클라이언트 - 인증 인터셉터 포함
// @MX:REASON: 모든 API 서비스가 이 Dio 인스턴스를 공유함
final dioProvider = Provider<Dio>((ref) {
  final authService = ref.watch(authServiceProvider);

  final dio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: AppConfig.apiTimeout,
    receiveTimeout: AppConfig.apiTimeout,
    sendTimeout: AppConfig.apiTimeout,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      // SPEC-SEC-001: API Key 인증 헤더 (--dart-define=API_KEY로 주입)
      if (AppConfig.apiKey.isNotEmpty) 'X-API-Key': AppConfig.apiKey,
    },
  ));

  // 인증 인터셉터 추가 (토큰 자동 주입 + 401 시 갱신)
  dio.interceptors.add(_AuthInterceptor(authService: authService, dio: dio));

  // 에러 로깅 인터셉터
  dio.interceptors.add(InterceptorsWrapper(
    onError: (DioException error, ErrorInterceptorHandler handler) {
      final statusCode = error.response?.statusCode;
      final message = error.message;
      // ignore: avoid_print
      print('[API 오류] 상태코드: $statusCode, 메시지: $message');
      handler.next(error);
    },
  ));

  return dio;
});

// 인증 인터셉터 구현체
class _AuthInterceptor extends Interceptor {
  final AuthService authService;
  // @MX:WARN: 토큰 갱신 전용 Dio - 인터셉터가 없는 별도 인스턴스
  // @MX:REASON: 동일 Dio 사용 시 갱신 요청이 인터셉터를 다시 통과해 무한루프 발생
  final Dio _refreshDio;

  _AuthInterceptor({required this.authService, required Dio dio})
      : _refreshDio = Dio(dio.options.copyWith());

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    // Authorization 헤더가 이미 있으면 건너뜀 (auth_api.dart에서 직접 설정한 경우)
    if (options.headers.containsKey('Authorization')) {
      return handler.next(options);
    }

    final token = await authService.getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    } else {
      // 게스트 토큰이 있으면 Bearer guest:<token> 형식으로 전송
      final guestToken = await authService.getGuestToken();
      if (guestToken != null) {
        options.headers['Authorization'] = 'Bearer guest:$guestToken';
      }
    }
    return handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    // 401 응답이고 갱신 시도 플래그가 없을 때만 갱신 시도
    if (err.response?.statusCode == 401 &&
        err.requestOptions.extra['_retried'] != true) {
      try {
        final refreshToken = await authService.getRefreshToken();
        if (refreshToken == null) {
          await authService.clearTokens();
          return handler.next(err);
        }

        // 갱신 요청
        final response = await _refreshDio.post(
          '/auth/refresh',
          data: {'refresh_token': refreshToken},
        );
        final newAccessToken = response.data['access_token'] as String;
        final newRefreshToken = response.data['refresh_token'] as String;
        await authService.saveTokens(newAccessToken, newRefreshToken);

        // 원래 요청 재시도
        final retryOptions = err.requestOptions.copyWith(
          headers: {
            ...err.requestOptions.headers,
            'Authorization': 'Bearer $newAccessToken',
          },
          extra: {...err.requestOptions.extra, '_retried': true},
        );
        final retryResponse = await _refreshDio.fetch(retryOptions);
        return handler.resolve(retryResponse);
      } catch (_) {
        // 갱신 실패 시 토큰 삭제 후 에러 전파
        await authService.clearTokens();
        return handler.next(err);
      }
    }

    return handler.next(err);
  }
}
