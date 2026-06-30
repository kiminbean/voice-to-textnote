import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  group('iOS microphone permission config', () {
    String readInfoPlist() {
      final plist = File('ios/Runner/Info.plist');
      expect(plist.existsSync(), isTrue);
      return plist.readAsStringSync();
    }

    test('Info.plist declares microphone usage description', () {
      expect(readInfoPlist(), contains('NSMicrophoneUsageDescription'));
    });

    test('Info.plist declares local network usage description', () {
      expect(readInfoPlist(), contains('NSLocalNetworkUsageDescription'));
    });

    test('Info.plist declares Google Sign-In client IDs and callback scheme',
        () {
      final plist = readInfoPlist();

      expect(plist, contains('GIDClientID'));
      expect(plist, contains('GIDServerClientID'));
      expect(
        plist,
        contains(
          'com.googleusercontent.apps.546416114080-456ie1r6jeolaitjfheaflsko521tqt0',
        ),
      );
    });

    test('Info.plist scopes insecure HTTP exception to staging host', () {
      final plist = readInfoPlist();

      expect(plist, contains('NSAllowsArbitraryLoads'));
      expect(plist, isNot(contains('NSAllowsLocalNetworking')));
      expect(plist, contains('NSExceptionDomains'));
      expect(plist, contains('100.69.69.119'));
      expect(plist, contains('NSExceptionAllowsInsecureHTTPLoads'));
    });

    test('iPhone orientations are locked to portrait', () {
      final plist = readInfoPlist();
      final iphoneOrientations = plist.substring(
        plist.indexOf('<key>UISupportedInterfaceOrientations</key>'),
        plist.indexOf('<key>UISupportedInterfaceOrientations~ipad</key>'),
      );

      expect(iphoneOrientations, contains('UIInterfaceOrientationPortrait'));
      expect(iphoneOrientations, isNot(contains('LandscapeLeft')));
      expect(iphoneOrientations, isNot(contains('LandscapeRight')));
    });

    test('Podfile enables permission_handler microphone group', () {
      final podfile = File('ios/Podfile');

      expect(podfile.existsSync(), isTrue);
      expect(
        podfile.readAsStringSync(),
        contains('PERMISSION_MICROPHONE=1'),
      );
    });
  });
}
