import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Android network security config', () {
    test('manifest references the network security config', () {
      final manifest = File('android/app/src/main/AndroidManifest.xml');

      expect(manifest.existsSync(), isTrue);
      expect(
        manifest.readAsStringSync(),
        contains(
            'android:networkSecurityConfig="@xml/network_security_config"'),
      );
    });

    test('main Android activity is locked to portrait', () {
      final manifest = File('android/app/src/main/AndroidManifest.xml');

      expect(manifest.existsSync(), isTrue);
      expect(
        manifest.readAsStringSync(),
        contains('android:screenOrientation="portrait"'),
      );
    });

    test('release/profile cleartext traffic is denied by default', () {
      final config =
          File('android/app/src/main/res/xml/network_security_config.xml');

      expect(config.existsSync(), isTrue);
      expect(
        config.readAsStringSync(),
        contains('<base-config cleartextTrafficPermitted="false">'),
      );
    });

    test('release/profile cleartext exception is scoped to staging host only',
        () {
      final config =
          File('android/app/src/main/res/xml/network_security_config.xml');
      final content = config.readAsStringSync();
      final domainTags =
          RegExp(r'<domain\b[^>]*>.*?</domain>').allMatches(content);

      expect(content,
          contains('<domain-config cleartextTrafficPermitted="true">'));
      expect(domainTags.length, 1);
      expect(content,
          contains('<domain includeSubdomains="false">100.69.69.119</domain>'));
      expect(content, isNot(contains('api.voicetextnote.com')));
    });

    test('debug cleartext exceptions are limited to local and staging hosts',
        () {
      final config =
          File('android/app/src/debug/res/xml/network_security_config.xml');
      final content = config.readAsStringSync();
      final cleartextBlock = RegExp(
        r'<domain-config cleartextTrafficPermitted="true">[\s\S]*?</domain-config>',
      ).firstMatch(content)?.group(0);

      expect(cleartextBlock, isNotNull);
      expect(cleartextBlock,
          contains('<domain includeSubdomains="false">localhost</domain>'));
      expect(cleartextBlock,
          contains('<domain includeSubdomains="false">100.69.69.119</domain>'));
      expect(cleartextBlock, isNot(contains('api.voicetextnote.com')));
    });
  });
}
