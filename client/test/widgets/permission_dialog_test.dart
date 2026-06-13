import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/widgets/permission_dialog.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('PermissionDialog & openAppSettings Tests', () {
    const permissionChannel = MethodChannel('flutter.baseflow.com/permissions/methods');
    const urlLauncherChannel = MethodChannel('plugins.flutter.io/url_launcher');
    final permissionLog = <MethodCall>[];
    final urlLauncherLog = <MethodCall>[];

    setUp(() {
      permissionLog.clear();
      urlLauncherLog.clear();

      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(permissionChannel, (MethodCall methodCall) async {
        permissionLog.add(methodCall);
        if (methodCall.method == 'openAppSettings') {
          return true;
        }
        return null;
      });

      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(urlLauncherChannel, (MethodCall methodCall) async {
        urlLauncherLog.add(methodCall);
        if (methodCall.method == 'canLaunch') {
          return false; // Force fallback to openAppSettingsIOS
        }
        return null;
      });
    });

    tearDown(() {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(permissionChannel, null);
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(urlLauncherChannel, null);
    });

    test('openAppSettings should call permission_handler openAppSettings and not recurse infinitely', () async {
      // Act
      final result = await openAppSettings();

      // Assert
      expect(result, isTrue);
      expect(permissionLog.length, equals(1));
      expect(permissionLog.first.method, equals('openAppSettings'));
    });

    testWidgets('PermissionDialog should trigger onOpenSettings callback when settings button is tapped', (WidgetTester tester) async {
      var openSettingsCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => showDialog(
                  context: context,
                  builder: (_) => PermissionDialog(
                    permissionType: PermissionType.notification,
                    onRequest: () {},
                    onOpenSettings: () => openSettingsCalled = true,
                  ),
                ),
                child: const Text('Show Dialog'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Tap "설정 열기" button
      await tester.tap(find.text('설정 열기'));
      await tester.pumpAndSettle();

      expect(openSettingsCalled, isTrue);
    });

    testWidgets('PermanentlyDeniedDialog should trigger onOpenSettings callback when settings button is tapped', (WidgetTester tester) async {
      var openSettingsCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => showDialog(
                  context: context,
                  builder: (_) => PermanentlyDeniedDialog(
                    permissionType: PermissionType.microphone,
                    onOpenSettings: () => openSettingsCalled = true,
                  ),
                ),
                child: const Text('Show Dialog'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Show Dialog'));
      await tester.pumpAndSettle();

      // Tap "설정 열기" button
      await tester.tap(find.text('설정 열기'));
      await tester.pumpAndSettle();

      expect(openSettingsCalled, isTrue);
    });

    group('PermissionDialog UI Texts', () {
      testWidgets('Microphone PermissionDialog shows correct texts', (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () => showDialog(
                    context: context,
                    builder: (_) => PermissionDialog(
                      permissionType: PermissionType.microphone,
                      onRequest: () {},
                      onOpenSettings: () {},
                    ),
                  ),
                  child: const Text('Show Dialog'),
                ),
              ),
            ),
          ),
        );

        await tester.tap(find.text('Show Dialog'));
        await tester.pumpAndSettle();

        expect(find.text('마이크 권한 필요'), findsOneWidget);
        expect(find.text('회의 녹음을 위해 마이크 접근 권한이 필요합니다.'), findsOneWidget);
        expect(find.text('권한 허용'), findsOneWidget);
      });

      testWidgets('Notification PermissionDialog shows correct texts', (WidgetTester tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () => showDialog(
                    context: context,
                    builder: (_) => PermissionDialog(
                      permissionType: PermissionType.notification,
                      onRequest: () {},
                      onOpenSettings: () {},
                    ),
                  ),
                  child: const Text('Show Dialog'),
                ),
              ),
            ),
          ),
        );

        await tester.tap(find.text('Show Dialog'));
        await tester.pumpAndSettle();

        expect(find.text('알림 권한 필요'), findsOneWidget);
        expect(find.text('녹음 완료 및 처리 완료 알림을 위해 알림 권한이 필요합니다.'), findsOneWidget);
        expect(find.text('설정 열기'), findsOneWidget);
      });
    });
  });
}
