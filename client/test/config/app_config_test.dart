// SPEC-ENV-001: 환경 설정 분리 명세 테스트
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/config/app_config.dart';

void main() {
  group('AppConfig 환경 설정', () {
    test('기본 API URL이 production HTTPS 서버를 가리켜야 한다', () {
      // --dart-define 없이 실행하는 릴리스 빌드가 HTTP staging에 묶이지 않아야 한다.
      expect(
        AppConfig.apiBaseUrl,
        equals('https://api.voicetextnote.com/api/v1'),
      );
      expect(Uri.parse(AppConfig.apiBaseUrl).scheme, equals('https'));
    });

    test('staging API URL은 명시 선택용 Tailscale 서버를 유지한다', () {
      expect(AppConfig.stagingApiBaseUrl, contains('100.69.69.119'));
    });

    test('Environment enum이 dev, staging, production 값을 가져야 한다', () {
      // 세 가지 환경 값이 모두 존재하는지 확인
      expect(Environment.values.length, equals(3));
      expect(Environment.values, contains(Environment.dev));
      expect(Environment.values, contains(Environment.staging));
      expect(Environment.values, contains(Environment.production));
    });

    test('기본 환경이 production이어야 한다', () {
      // --dart-define=ENV 없이 실행 시 production이 기본값
      expect(AppConfig.environment, equals(Environment.production));
    });

    test('production 환경에서 isDebugMode가 false이어야 한다', () {
      expect(AppConfig.isDebugMode, isFalse);
    });
  });
}
