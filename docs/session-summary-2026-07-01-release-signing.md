# Session Summary: Release Signing and Strict Gate

Date: 2026-07-01

## What changed

- Verified SSH access to `IBui-MacBookPro.local` with `~/.ssh/id_ed25519_voice_release`.
- Confirmed the MacBook repo was still on `b650ebb` and had only an Apple Development signing identity at the time of CLI inspection.
- Confirmed the active production signing evidence is from the Mac mini, not the MacBook automatic signing state.
- Created and installed a dedicated App Store distribution signing setup on the Mac mini.
- Produced a signed iOS release archive:
  `/Users/ibkim/secure/voice-to-textnote/apple-signing/Runner-production-final-20260701191705.xcarchive`
- Extracted production entitlements to `docs/ios-release-entitlements.plist`.
- Updated `docs/release-e2e-evidence.json` with current git revision, artifact hashes, device metadata, and the production entitlement SHA-256.
- Fixed the release readiness checker so the tracked release evidence can contain either a scaffold SHA-256 value or a real entitlement SHA-256 value.
- Fixed the release evidence git revision check so a committed evidence file can reference the actually tested revision when only docs, tests, or release tooling changed afterward. If runtime source changes after the tested revision, strict readiness still fails.
- Rebuilt the Android private staging release with `ENV=staging` and `API_BASE_URL=http://100.69.69.119:8000/api/v1` so the installed release app no longer boots to a blank production-placeholder screen.
- Installed the Android staging release on `76aadc20` and verified the login/home/result/share flows on the physical Redmi Note 9 Pro.
- Filled real Android E2E evidence for four strict scenarios: `android_foreground_service`, `android_debug_tailscale_cleartext_allowed`, `android_release_cleartext_blocked`, and `export_share_android`.
- Re-ran the Android Promise Radar device gate on the same installed staging release. The first run failed because Android was still focused on the MIUI system share sheet, not the app result screen. After returning home and relaunching `com.voicetextnote.app`, the result screen restored `약속 레이더` as `탭 12개 중 4번째`, and `verify_promise_radar_device_gate.py` passed.
- Added an iOS `RunnerUITests` target for physical-device launch evidence.
- Fixed the Mac mini user keychain search list so `xcodebuild test` can see both the dedicated release signing keychain and `login.keychain-db`; the previous keychain list contained a malformed `login.keychain-db -db` entry.
- Verified the iOS Debug/XCUITest crash as a Flutter 3.44.1 engine debug-path issue on iPhone 17 Pro iOS 26.5.1, with crash frames in `VSyncClient` and `createTouchRateCorrectionVSyncClientIfNeeded` before Dart code runs.
- Verified iOS Release/XCUITest launch smoke on the same physical iPhone and exported screenshot/UI hierarchy attachments for future strict evidence work.

## Current private values to configure locally

Do not commit private key contents. The paths below are local secure paths only.

```text
APNS_AUTH_KEY_PATH=/Users/ibkim/secure/voice-to-textnote/AuthKey_362893TR3Z.p8
APNS_KEY_ID=362893TR3Z
APNS_TEAM_ID=4NJ9JSQFW9
APP_STORE_CONNECT_API_KEY_PATH=/Users/ibkim/secure/voice-to-textnote/AuthKey_5WDG3L7L32.p8
APP_STORE_CONNECT_KEY_ID=5WDG3L7L32
APP_STORE_CONNECT_ISSUER_ID=3af9f2b0-aefc-4670-a821-1606fb19e086
IOS_RELEASE_ENTITLEMENTS_PATH=docs/ios-release-entitlements.plist
FIREBASE_CREDENTIALS_PATH=/Users/ibkim/secure/voice-to-textnote/firebase-adminsdk-fbsvc.json
```

## Production entitlement evidence

```text
application-identifier: 4NJ9JSQFW9.com.voicetextnote.app
aps-environment: production
get-task-allow: false
team-identifier: 4NJ9JSQFW9
ios_entitlements_sha256: e44b8d040b5abe77085420d347e186850201db6111dd89c8819b39c664924bd3
```

## Verification evidence

- `codesign -d --entitlements :- Runner.app` showed `aps-environment=production` and `get-task-allow=false`.
- `python3 client/scripts/verify_release_readiness.py` -> `release_readiness: 0 errors, 2 warnings`.
- `.venv/bin/pytest backend/tests/test_release_readiness_evidence.py::test_tracked_release_e2e_scaffold_matches_strict_top_level_schema backend/tests/test_release_readiness_evidence.py::test_tracked_release_e2e_scaffold_check_rejects_stale_platforms --no-cov -q` -> `2 passed`.
- `.venv/bin/ruff check client/scripts/verify_release_readiness.py backend/tests/test_release_readiness_evidence.py` -> `All checks passed!`.
- Strict run after Android physical-device evidence updates and local DB FCM token injection -> `release_readiness: 17 errors, 1 warnings`.
- `ANDROID_DEVICE_SERIAL=76aadc20 IOS_DEVICE_UDID=C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA python3 client/scripts/verify_mobile_release_runner.py` -> `mobile_release_runner: 0 errors, 1 warnings`.
- `./gradlew :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.voicetextnote.app.NetworkSecurityPolicyInstrumentedTest` -> `BUILD SUCCESSFUL`, `Finished 1 tests on Redmi Note 9 Pro - 12`.
- `flutter build apk --release --dart-define=ENV=staging --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1 --dart-define=API_KEY=<local env>` -> built `client/build/app/outputs/flutter-apk/app-release.apk`, SHA-256 `d75e70b96a30e03988a292658ef51086fbe67f19b8c084d28ff6744c6432ec2a`.
- `adb -s 76aadc20 install -r client/build/app/outputs/flutter-apk/app-release.apk` -> `Success`.
- `python3 client/scripts/verify_promise_radar_device_gate.py --serial 76aadc20 --evidence-out docs/promise-radar-android-device-gate-2026-07-01-current.json` -> `PASS Promise Radar Android device gate`.
- `xcrun devicectl device info details --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA` -> iPhone `available`, `wired`, Developer Mode enabled, CoreDevice tunnel connected.
- `flutter screenshot -d 00008150-000239020C08401C` -> `Screenshot not supported for Inbean의 iPhone`.
- `uvx --from pymobiledevice3 pymobiledevice3 usbmux list` -> `[]`.
- `uvx --from pymobiledevice3 pymobiledevice3 remote browse --timeout 5` -> `ERROR This command requires root privileges. Consider retrying with "sudo".`
- `security find-identity -v -p codesigning` after keychain search-list repair -> 4 valid code-signing identities including Apple Distribution and Apple Development identities.
- `xcodebuild test -workspace ios/Runner.xcworkspace -scheme Runner -configuration Debug -destination 'id=00008150-000239020C08401C' -only-testing:RunnerUITests/RunnerUITests/testReleaseLaunchEvidence` -> app crash before Dart code in Flutter engine `VSyncClient`; reproduced in `docs/release-e2e-artifacts/ios_release_launch_xcuitest_20260701205638.xcresult`.
- `xcodebuild test -workspace ios/Runner.xcworkspace -scheme Runner -configuration Release -destination 'id=00008150-000239020C08401C' -only-testing:RunnerUITests/RunnerUITests/testReleaseLaunchEvidence` -> `Test Case '-[RunnerUITests.RunnerUITests testReleaseLaunchEvidence]' passed (5.901 seconds)`, `Executed 1 test, with 0 failures (0 unexpected)`, `** TEST SUCCEEDED **`.
- Final iOS Release launch evidence bundle: `docs/release-e2e-artifacts/ios_release_launch_xcuitest_release_20260701205837.xcresult`.
- Final iOS Release launch exported attachments: `docs/release-e2e-artifacts/ios_release_launch_xcuitest_release_20260701205837_attachments/`.

## Remaining blockers

- 17 strict release E2E scenarios remain. They are iOS-only or Android+iOS common scenarios: permission recovery, unfinished recording recovery, push/deeplink, iOS background/interruption/Bluetooth/HTTP/share, and Promise Radar status/push/calendar/assignee quality.
- iOS physical launch evidence is no longer blocked: use Release configuration `RunnerUITests` attachments. `devicectl`/`flutter screenshot` still cannot provide noninteractive physical iPhone screenshots, so scenario-specific iOS evidence should be collected by extending `RunnerUITests`.
- Debug/XCUITest Flutter engine `VSyncClient` crashes should not be treated as release blockers while Release/XCUITest passes on the same device. Re-check this only after Flutter upgrade or iOS engine changes.
- Do not fabricate scenario evidence just to pass strict readiness.
