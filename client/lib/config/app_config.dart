// 앱 전역 설정 상수
class AppConfig {
  // API 기본 URL (백엔드 서버)
  static const String apiBaseUrl = 'http://100.110.255.105:8000/api/v1';

  // API 요청 타임아웃 시간 (일반 API 호출용)
  static const Duration apiTimeout = Duration(seconds: 30);

  // 파일 업로드 전용 타임아웃 (대용량 오디오 파일 전송용)
  static const Duration uploadSendTimeout = Duration(minutes: 10);
  static const Duration uploadReceiveTimeout = Duration(minutes: 2);

  // 파이프라인 상태 폴링 간격
  static const Duration pollingInterval = Duration(seconds: 3);
}
