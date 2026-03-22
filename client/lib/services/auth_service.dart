// 토큰 라이프사이클 관리 서비스 (SecureStorage 기반)
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:jwt_decoder/jwt_decoder.dart';

// SecureStorage 키 상수
const _kAccessToken = 'access_token';
const _kRefreshToken = 'refresh_token';

// AuthService 프로바이더
final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService();
});

// @MX:ANCHOR: 토큰 저장/조회/삭제를 담당하는 핵심 서비스 - 인터셉터에서 직접 사용
// @MX:REASON: dioProvider와 authStateProvider 양쪽에서 의존하므로 독립 유지 필수
class AuthService {
  final FlutterSecureStorage _storage;

  AuthService() : _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  // 토큰 쌍 저장
  Future<void> saveTokens(String accessToken, String refreshToken) async {
    await Future.wait([
      _storage.write(key: _kAccessToken, value: accessToken),
      _storage.write(key: _kRefreshToken, value: refreshToken),
    ]);
  }

  // 액세스 토큰 조회
  Future<String?> getAccessToken() async {
    return _storage.read(key: _kAccessToken);
  }

  // 리프레시 토큰 조회
  Future<String?> getRefreshToken() async {
    return _storage.read(key: _kRefreshToken);
  }

  // 토큰 전체 삭제 (로그아웃 시)
  Future<void> clearTokens() async {
    await Future.wait([
      _storage.delete(key: _kAccessToken),
      _storage.delete(key: _kRefreshToken),
    ]);
  }

  // 액세스 토큰 만료 여부 확인
  Future<bool> isAccessTokenExpired() async {
    final token = await getAccessToken();
    if (token == null) return true;
    try {
      return JwtDecoder.isExpired(token);
    } catch (_) {
      // 파싱 실패 시 만료로 간주
      return true;
    }
  }

  // 토큰 존재 여부 확인 (빠른 체크용)
  Future<bool> hasTokens() async {
    final token = await getAccessToken();
    return token != null && token.isNotEmpty;
  }
}
