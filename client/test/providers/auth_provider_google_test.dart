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
  });
}
