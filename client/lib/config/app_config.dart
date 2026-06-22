// 앱 환경 설정 — SPEC-ENV-001
// @MX:ANCHOR: [AUTO] AppConfig.apiBaseUrl은 api_client, auth_api, processing_screen 3곳에서 참조
// @MX:REASON: 환경별 URL 분기의 핵심 계약 지점

/// 앱 실행 환경을 나타내는 열거형
enum Environment {
  /// 로컬 개발 환경 (localhost)
  dev,

  /// 스테이징 환경 (Tailscale IP)
  staging,

  /// 프로덕션 환경 (도메인)
  production,
}

class AppConfig {
  // 컴파일 시 --dart-define=ENV=dev|staging|production 으로 주입 가능
  // 기본값: staging (기존 동작 유지)
  static const String _envName =
      String.fromEnvironment('ENV', defaultValue: 'staging');

  // 컴파일 시 --dart-define=API_BASE_URL=https://... 으로 직접 URL 지정 가능
  // 비어 있으면 환경별 기본 URL 사용
  static const String _apiBaseUrlOverride =
      String.fromEnvironment('API_BASE_URL', defaultValue: '');

  // 컴파일 시 --dart-define=API_KEY=xxx 으로 API Key 주입
  // 서버의 X-API-Key 인증에 사용됨 (SPEC-SEC-001)
  static const String apiKey =
      String.fromEnvironment('API_KEY', defaultValue: '');

  /// 현재 실행 환경
  static Environment get environment {
    switch (_envName) {
      case 'dev':
        return Environment.dev;
      case 'production':
        return Environment.production;
      default:
        // 'staging' 또는 알 수 없는 값은 staging 처리
        return Environment.staging;
    }
  }

  /// API 기본 URL
  /// 우선순위: --dart-define=API_BASE_URL > 환경별 기본값
  static String get apiBaseUrl {
    if (_apiBaseUrlOverride.isNotEmpty) return _apiBaseUrlOverride;
    switch (environment) {
      case Environment.dev:
        return 'http://localhost:8000/api/v1';
      case Environment.staging:
        return 'http://100.69.69.119:8000/api/v1';
      case Environment.production:
        return 'https://api.voicetextnote.com/api/v1';
    }
  }

  /// 디버그 모드 여부 (production이 아닌 환경에서 true)
  static bool get isDebugMode => environment != Environment.production;

  // API 요청 타임아웃 시간 (일반 API 호출용)
  static const Duration apiTimeout = Duration(seconds: 30);

  // 파일 업로드 전용 타임아웃 (대용량 오디오 파일 전송용)
  static const Duration uploadSendTimeout = Duration(minutes: 10);
  static const Duration uploadReceiveTimeout = Duration(minutes: 2);

  // 파이프라인 상태 폴링 간격
  static const Duration pollingInterval = Duration(seconds: 3);
}
