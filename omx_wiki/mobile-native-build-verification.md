# Mobile Native Build Verification

Category: environment
Tags: mobile, android, ios, flutter, cocoapods, gradle
Updated: 2026-06-14

## Current State

Native mobile verification is now proven locally for `client`.

- Android SDK root: `/Users/ibkim/Library/Android/sdk`
- Flutter Android SDK config: `flutter config --android-sdk /Users/ibkim/Library/Android/sdk`
- Android toolchain proof: `flutter doctor -v` reports `Android SDK version 36.0.0` and `All Android licenses accepted`.
- Android build proof: `flutter build apk --debug` reports `✓ Built build/app/outputs/flutter-apk/app-debug.apk`.
- iOS dependency proof: `cd client/ios && pod install` reports `Pod installation complete!`.
- iOS build proof: `flutter build ios --debug --no-codesign` reports `✓ Built build/ios/iphoneos/Runner.app`.
- Full gate proof: `cd client && ./scripts/verify_mobile.sh --native` passes analyze, tests, local STT smoke, Android APK build, and iOS no-codesign build.

## Installed Android SDK Packages

- `platforms;android-36`
- `build-tools;36.0.0`
- `build-tools;28.0.3`
- `platform-tools`
- `cmdline-tools;latest`
- `ndk;27.0.12077973`
- `cmake;3.22.1`

## Repository Fixes

- `client/android/gradlew`, `client/android/gradlew.bat`, and `client/android/gradle/wrapper/*` restore wrapper-based Android builds.
- `client/android/settings.gradle` includes Flutter Gradle plugin composite build and pins AGP/Kotlin/Google Services plugin versions.
- `client/android/build.gradle` pins AGP 8.11.1.
- `client/android/app/build.gradle` uses `compileSdk 36`, Java 17, core library desugaring, and release `shrinkResources false`.
- `client/android/app/src/main/kotlin/com/voicetextnote/app/RecordingService.kt` uses existing `R.mipmap.ic_launcher` for the foreground notification icon.
- `.github/workflows/mobile.yml` installs Android SDK 36 and build-tools in CI.
- `client/ios/Flutter/Profile.xcconfig` includes `Pods-Runner.profile.xcconfig` and `Generated.xcconfig`.
- `client/ios/Runner.xcodeproj/project.pbxproj` wires Runner Profile to `Profile.xcconfig`.
- `client/ios/Runner/AppDelegate.swift` uses Swift `FlutterResult` callback style for MethodChannel responses.

## Warnings To Remember

- Flutter currently warns that app/plugins using Kotlin Gradle Plugin should migrate to Built-in Kotlin in a future Flutter release. This is not a current build failure.
- Do not commit machine-specific `sdk.dir` from `client/android/local.properties`.
- `.omx/metrics.json` and `.omx/state/tmux-hook-state.json` are runtime state, not project documentation.
