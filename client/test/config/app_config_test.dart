// SPEC-ENV-001: 환경 설정 분리 명세 테스트
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/config/app_config.dart';

void main() {
  group('AppConfig 환경 설정', () {
    test('기본 API URL이 staging 서버를 가리켜야 한다', () {
      // 기본 환경(staging)의 API URL은 현재 하드코딩 값과 동일해야 한다
      // --dart-define 없이 실행하면 staging 기본값 사용
      expect(
        AppConfig.apiBaseUrl,
        equals(AppConfig.stagingApiBaseUrl),
      );
      expect(AppConfig.stagingApiBaseUrl, contains('100.69.69.119'));
    });

    test('Environment enum이 dev, staging, production 값을 가져야 한다', () {
      // 세 가지 환경 값이 모두 존재하는지 확인
      expect(Environment.values.length, equals(3));
      expect(Environment.values, contains(Environment.dev));
      expect(Environment.values, contains(Environment.staging));
      expect(Environment.values, contains(Environment.production));
    });

    test('기본 환경이 staging이어야 한다', () {
      // --dart-define=ENV 없이 실행 시 staging이 기본값
      expect(AppConfig.environment, equals(Environment.staging));
    });

    test('staging 환경에서 isDebugMode가 true이어야 한다', () {
      // production이 아닌 환경에서는 디버그 모드 활성화
      expect(AppConfig.isDebugMode, isTrue);
    });
  });
}
