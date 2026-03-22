// 인증 관련 API 호출 서비스 (Dio 래핑)
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:voice_to_textnote/config/app_config.dart';
import 'package:voice_to_textnote/models/auth_user.dart';

// AuthApi 프로바이더 (인터셉터 없는 순수 Dio 사용 - 순환 의존 방지)
// @MX:WARN: 인터셉터가 붙은 dioProvider를 사용하지 말 것
// @MX:REASON: 토큰 갱신 시 인터셉터가 개입하면 무한루프 발생
final authApiProvider = Provider<AuthApi>((ref) {
  // 인터셉터 없는 별도 Dio 인스턴스 생성
  final dio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: AppConfig.apiTimeout,
    receiveTimeout: AppConfig.apiTimeout,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  ));
  return AuthApi(dio);
});

class AuthApi {
  final Dio _dio;

  AuthApi(this._dio);

  // 회원가입
  Future<AuthResponse> register({
    required String email,
    required String password,
    required String displayName,
  }) async {
    final response = await _dio.post(
      '/auth/register',
      data: {
        'email': email,
        'password': password,
        'display_name': displayName,
      },
    );
    return AuthResponse.fromJson(response.data as Map<String, dynamic>);
  }

  // 로그인
  Future<AuthResponse> login({
    required String email,
    required String password,
  }) async {
    final response = await _dio.post(
      '/auth/login',
      data: {
        'email': email,
        'password': password,
      },
    );
    return AuthResponse.fromJson(response.data as Map<String, dynamic>);
  }

  // 토큰 갱신
  Future<TokenResponse> refresh(String refreshToken) async {
    final response = await _dio.post(
      '/auth/refresh',
      data: {'refresh_token': refreshToken},
    );
    return TokenResponse.fromJson(response.data as Map<String, dynamic>);
  }

  // 로그아웃
  Future<void> logout({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _dio.post(
      '/auth/logout',
      data: {'refresh_token': refreshToken},
      options: Options(
        headers: {'Authorization': 'Bearer $accessToken'},
      ),
    );
  }

  // 현재 사용자 정보 조회
  Future<AuthUser> getMe(String accessToken) async {
    final response = await _dio.get(
      '/auth/me',
      options: Options(
        headers: {'Authorization': 'Bearer $accessToken'},
      ),
    );
    return AuthUser.fromJson(response.data as Map<String, dynamic>);
  }
}
