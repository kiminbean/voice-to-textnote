// SPEC-MOBILE-002: 전사 처리 출처 열거형
enum TranscriptionSource {
  server,
  local,
  hybrid,
  ;

  static TranscriptionSource fromString(String? value) {
    switch (value?.toLowerCase()) {
      case 'local':
        return TranscriptionSource.local;
      case 'hybrid':
        return TranscriptionSource.hybrid;
      default:
        return TranscriptionSource.server;
    }
  }

  String get label {
    switch (this) {
      case TranscriptionSource.server:
        return '서버';
      case TranscriptionSource.local:
        return '오프라인';
      case TranscriptionSource.hybrid:
        return '하이브리드';
    }
  }
}
