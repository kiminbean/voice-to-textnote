// 앱 전역 설정 상수
class AppConfig {
  // API 기본 URL (백엔드 서버)
  static const String apiBaseUrl = 'http://100.110.255.105:8000/api/v1';

  // API 요청 타임아웃 시간
  static const Duration apiTimeout = Duration(seconds: 30);

  // 파이프라인 상태 폴링 간격
  static const Duration pollingInterval = Duration(seconds: 2);
}
