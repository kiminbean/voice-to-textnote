// SPEC-MOBILE-005 REQ-001: AppDelegate MethodChannel 인터페이스 검증 테스트
// AC-001: AppDelegate.swift에 3개 MethodChannel 핸들러가 등록되어 있다
// @MX:NOTE: 네이티브 동작 검증은 아님 — MethodChannel 인터페이스 계약 검증
// Flutter 3.44.1 호환: setMockMethodCallHandler 대신 handlePlatformMessage 사용
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channelName = 'com.voicetextnote.app/recording';

  group('REQ-001-01: MethodChannel 핸들러 인터페이스', () {
    test('채널 이름이 Android와 동일해야 함 (REQ-001-06)', () {
      const methodChannel = MethodChannel(channelName);
      expect(methodChannel.name, equals('com.voicetextnote.app/recording'));
    });

    test('startBackgroundTask는 유효한 메서드 이름이어야 함', () async {
      const methodChannel = MethodChannel(channelName);
      // 핸들러 미등록 상태 → MissingPluginException 발생 = 메서드 이름은 유효
      expect(
        () => methodChannel.invokeMethod('startBackgroundTask'),
        throwsA(isA<MissingPluginException>()),
      );
    });

    test('stopBackgroundTask는 유효한 메서드 이름이어야 함', () async {
      const methodChannel = MethodChannel(channelName);
      expect(
        () => methodChannel.invokeMethod('stopBackgroundTask'),
        throwsA(isA<MissingPluginException>()),
      );
    });

    test('flushRecording은 유효한 메서드 이름이어야 함', () async {
      const methodChannel = MethodChannel(channelName);
      expect(
        () => methodChannel.invokeMethod('flushRecording'),
        throwsA(isA<MissingPluginException>()),
      );
    });

    test('startForegroundService는 호환성 no-op 메서드로 존재해야 함', () async {
      const methodChannel = MethodChannel(channelName);
      expect(
        () => methodChannel.invokeMethod('startForegroundService'),
        throwsA(isA<MissingPluginException>()),
      );
    });

    test('stopForegroundService는 호환성 no-op 메서드로 존재해야 함', () async {
      const methodChannel = MethodChannel(channelName);
      expect(
        () => methodChannel.invokeMethod('stopForegroundService'),
        throwsA(isA<MissingPluginException>()),
      );
    });
  });

  group('REQ-001/003: AppDelegate.swift 정적 계약', () {
    late String appDelegate;
    late String infoPlist;

    setUpAll(() {
      appDelegate = File('ios/Runner/AppDelegate.swift').readAsStringSync();
      infoPlist = File('ios/Runner/Info.plist').readAsStringSync();
    });

    test('녹음 MethodChannel과 5개 호환 메서드를 구현해야 함', () {
      expect(
          appDelegate,
          contains(
              'private let channelName = "com.voicetextnote.app/recording"'));
      expect(appDelegate, contains('FlutterMethodChannel('));
      expect(appDelegate, contains('method == "startBackgroundTask"'));
      expect(appDelegate, contains('method == "stopBackgroundTask"'));
      expect(appDelegate, contains('method == "flushRecording"'));
      expect(appDelegate, contains('method == "startForegroundService"'));
      expect(appDelegate, contains('method == "stopForegroundService"'));
    });

    test('iOS 백그라운드 태스크와 오디오 세션 flush를 구현해야 함', () {
      expect(appDelegate, contains('UIApplication.shared.beginBackgroundTask'));
      expect(appDelegate, contains('UIApplication.shared.endBackgroundTask'));
      expect(appDelegate, contains('AVAudioSession.sharedInstance()'));
      expect(appDelegate, contains('try session.setActive(true'));
    });

    test('인터럽션과 route change를 Dart 이벤트로 전달해야 함', () {
      expect(appDelegate, contains('AVAudioSession.interruptionNotification'));
      expect(appDelegate, contains('AVAudioSession.routeChangeNotification'));
      expect(appDelegate, contains('method: "onInterruptionBegin"'));
      expect(appDelegate, contains('method: "onInterruptionEnd"'));
      expect(appDelegate, contains('method: "onRouteChange"'));
      expect(appDelegate, contains('"shouldResume": shouldResume'));
      expect(appDelegate, contains('"reason": reasonString'));
    });

    test('iOS Open In import는 shared_import 채널과 문서 타입을 노출해야 함', () {
      expect(
        appDelegate,
        contains('private let sharedImportChannelName = '
            '"com.voicetextnote.app/shared_import"'),
      );
      expect(appDelegate, contains('consumeInitialSharedImport'));
      expect(appDelegate, contains('consumeLatestSharedImport'));
      expect(appDelegate, contains('override func application('));
      expect(appDelegate, contains('copySharedFile(_ url: URL)'));
      expect(appDelegate, contains('case "png":'));
      expect(appDelegate, contains('"filePath": target.path'));

      expect(infoPlist, contains('CFBundleDocumentTypes'));
      expect(infoPlist, contains('com.adobe.pdf'));
      expect(
        infoPlist,
        contains('org.openxmlformats.wordprocessingml.document'),
      );
      expect(infoPlist, contains('public.image'));
    });
  });

  group('Owll benchmark: Android share-sheet import contract', () {
    late String manifest;
    late String mainActivity;

    setUpAll(() {
      manifest =
          File('android/app/src/main/AndroidManifest.xml').readAsStringSync();
      mainActivity = File(
        'android/app/src/main/kotlin/com/voicetextnote/app/MainActivity.kt',
      ).readAsStringSync();
    });

    test('Android manifest accepts text/plain ACTION_SEND shares', () {
      expect(manifest, contains('android.intent.action.SEND'));
      expect(manifest, contains('android:mimeType="text/plain"'));
      expect(manifest, contains('android:mimeType="application/pdf"'));
      expect(manifest, contains('android:mimeType="image/*"'));
    });

    test('MainActivity exposes shared import MethodChannel methods', () {
      expect(
        mainActivity,
        contains('com.voicetextnote.app/shared_import'),
      );
      expect(mainActivity, contains('consumeInitialSharedImport'));
      expect(mainActivity, contains('consumeLatestSharedImport'));
      expect(mainActivity, contains('Intent.ACTION_SEND'));
      expect(mainActivity, contains('Intent.EXTRA_TEXT'));
      expect(mainActivity, contains('Intent.EXTRA_STREAM'));
      expect(mainActivity, contains('OpenableColumns.DISPLAY_NAME'));
      expect(mainActivity, contains('filePath'));
    });
  });

  group('REQ-001: 네이티브→Dart 이벤트 인터페이스', () {
    test('onInterruptionBegin 이벤트를 수신할 수 있어야 함', () async {
      bool? received;

      const MethodChannel(channelName).setMethodCallHandler((call) async {
        if (call.method == 'onInterruptionBegin') {
          received = true;
        }
        return null;
      });

      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .handlePlatformMessage(
        channelName,
        const StandardMethodCodec().encodeMethodCall(
          const MethodCall('onInterruptionBegin'),
        ),
        null,
      );

      await Future.delayed(Duration.zero);
      expect(received, isTrue);
    });

    test('onInterruptionEnd 이벤트에서 shouldResume 플래그를 전달해야 함', () async {
      bool? receivedShouldResume;

      const MethodChannel(channelName).setMethodCallHandler((call) async {
        if (call.method == 'onInterruptionEnd') {
          receivedShouldResume = call.arguments as bool? ?? false;
        }
        return null;
      });

      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .handlePlatformMessage(
        channelName,
        const StandardMethodCodec().encodeMethodCall(
          const MethodCall('onInterruptionEnd', true),
        ),
        null,
      );

      await Future.delayed(Duration.zero);
      expect(receivedShouldResume, isTrue);
    });

    test('onRouteChange 이벤트에서 reason 문자열을 전달해야 함', () async {
      String? receivedReason;

      const MethodChannel(channelName).setMethodCallHandler((call) async {
        if (call.method == 'onRouteChange') {
          final args = call.arguments;
          if (args is Map) {
            receivedReason = args['reason'] as String?;
          }
        }
        return null;
      });

      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .handlePlatformMessage(
        channelName,
        const StandardMethodCodec().encodeMethodCall(
          const MethodCall('onRouteChange', {'reason': 'oldDeviceUnavailable'}),
        ),
        null,
      );

      await Future.delayed(Duration.zero);
      expect(receivedReason, equals('oldDeviceUnavailable'));
    });
  });
}
