import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';

void main() {
  group('Google sign-in configuration', () {
    test('iOS Google sign-in has bundled OAuth client IDs', () {
      expect(googleIosClientId, isNotEmpty);
      expect(googleServerClientId, isNotEmpty);
      expect(googleClientIdForPlatform(isIOS: true), googleIosClientId);
      expect(isGoogleSignInConfiguredForPlatform(isIOS: true), isTrue);
    });

    test('macOS Google sign-in has bundled OAuth client IDs', () {
      expect(googleMacosClientId, isNotEmpty);
      expect(googleServerClientId, isNotEmpty);
      expect(
        googleClientIdForPlatform(isIOS: false, isMacOS: true),
        googleMacosClientId,
      );
      expect(
        isGoogleSignInConfiguredForPlatform(isIOS: false, isMacOS: true),
        isTrue,
      );
    });

    test('non-iOS platforms require the server client ID', () {
      expect(googleServerClientId, isNotEmpty);
      expect(googleClientIdForPlatform(isIOS: false), isNull);
      expect(isGoogleSignInConfiguredForPlatform(isIOS: false), isTrue);
    });

    test('Android clears the previous Google account selection first', () {
      expect(shouldClearGoogleSelectionBeforeSignIn(isIOS: false), isTrue);
    });

    test('iOS keeps the existing Google sign-in behavior', () {
      expect(shouldClearGoogleSelectionBeforeSignIn(isIOS: true), isFalse);
    });

    test('Android OAuth registration errors show configuration guidance', () {
      final message = socialLoginErrorMessage(
        PlatformException(
          code: 'sign_in_failed',
          message:
              'This android application is not registered to use OAuth2.0.',
        ),
        'Google',
      );

      expect(message, contains('Google 로그인 설정에 문제가 있습니다'));
      expect(message, contains('앱 서명과 OAuth 클라이언트 설정'));
    });

    test('Google DEVELOPER_ERROR status shows configuration guidance', () {
      final message = socialLoginErrorMessage(
        Exception('DEVELOPER_ERROR: server client id is invalid'),
        'Google',
      );

      expect(message, contains('Google 로그인 설정에 문제가 있습니다'));
    });
  });
}
