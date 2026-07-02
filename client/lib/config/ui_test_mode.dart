import 'dart:io' show Platform;

import 'package:flutter/services.dart';

class UiTestMode {
  const UiTestMode._();

  static const MethodChannel _recordingChannel =
      MethodChannel('com.voicetextnote.app/recording');

  static bool get enabled {
    if (const bool.fromEnvironment('VOICE_TEXTNOTE_UI_TEST')) {
      return true;
    }
    if (Platform.environment['VOICE_TEXTNOTE_UI_TEST'] == '1') {
      return true;
    }
    if (Platform.executableArguments.contains('--voice-textnote-ui-test')) {
      return true;
    }
    return Platform.environment.keys.any(_looksLikeXCTestMarker) ||
        Platform.executableArguments.any(_looksLikeXCTestMarker);
  }

  static Future<bool> detect() async {
    if (enabled) {
      return true;
    }
    for (var attempt = 0; attempt < 8; attempt++) {
      try {
        final nativeMode =
            await _recordingChannel.invokeMethod<bool>('isUiTestMode') ?? false;
        if (nativeMode) {
          return true;
        }
      } catch (_) {
        // The native channel can be unavailable during very early startup.
      }
      await Future<void>.delayed(const Duration(milliseconds: 100));
    }
    return false;
  }

  static bool _looksLikeXCTestMarker(String value) {
    final normalized = value.toLowerCase();
    return normalized.contains('xctest') ||
        normalized.contains('uitest') ||
        normalized.contains('runneruitests');
  }
}
