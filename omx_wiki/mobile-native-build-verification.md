# Mobile Native Build Verification

Category: environment
Tags: mobile, android, ios, flutter, cocoapods, gradle
Updated: 2026-06-30

## Current State

Native mobile verification is now proven locally for `client`.

- Android SDK root: `/Users/ibkim/Library/Android/sdk`
- Flutter Android SDK config: `flutter config --android-sdk /Users/ibkim/Library/Android/sdk`
- Android toolchain proof: `flutter doctor -v` reports `Android SDK version 36.0.0` and `All Android licenses accepted`.
- Android build proof: `flutter build apk --debug` reports `✓ Built build/app/outputs/flutter-apk/app-debug.apk`.
- iOS dependency proof: `cd client/ios && pod install` reports `Pod installation complete!`.
- iOS build proof: `flutter build ios --debug --no-codesign` reports `✓ Built build/ios/iphoneos/Runner.app`.
- Full gate proof: `cd client && ./scripts/verify_mobile.sh --native` passes analyze, tests, local STT smoke, Android APK build, and iOS no-codesign build.
- Android release proof: `flutter build apk --release --target-platform android-arm64` builds `client/build/app/outputs/flutter-apk/app-release.apk`.
- iOS release proof: `flutter build ipa --release` builds `client/build/ios/ipa/Voice TextNote.ipa` and `client/build/ios/archive/Runner.xcarchive`.
- iOS device install proof: `xcrun devicectl device install app --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA build/ios/archive/Runner.xcarchive/Products/Applications/Runner.app` installs `com.voicetextnote.app`; `devicectl device process launch` launches it.

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
- Do not commit local Android signing material. `client/android/key.properties`, `client/android/*.jks`, and `client/build/` are local artifacts.
- Flutter may report `enable Developer Mode` for iOS even when CoreDevice reports `developerModeStatus: enabled`. Trust `xcrun devicectl device info details` for the final device state and install the signed archive app directly with `devicectl` when Flutter install is stale.
- Android Google Sign-In release testing depends on the installed APK signing SHA-1 being registered in Google Cloud/Firebase for `com.voicetextnote.app`. On 2026-06-30 the local test release APK SHA-1 was `1F:84:A6:04:D6:18:F5:17:EE:AC:5D:6D:5A:D5:EE:62:B0:C0:FC:66`.
