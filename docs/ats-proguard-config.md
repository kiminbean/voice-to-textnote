# ATS / ProGuard 설정 문서 (T-018)

**SPEC-MOBILE-004 | 작성일: 2026-06-13**

---

## iOS App Transport Security (ATS)

### 현재 상태

`Info.plist`는 release 기준으로 임의 HTTP 로드를 차단한다.

```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <false/>
</dict>
```

### 프로덕션 정책

프로덕션 iOS 빌드에는 `NSExceptionAllowsInsecureHTTPLoads: true` 도메인 예외를 두지 않는다.
로컬/Tailscale HTTP 테스트는 Android debug network security config 또는 개발 전용 실행 인자로 제한하고,
iOS release E2E에서는 HTTP 요청이 ATS에 의해 차단되는 것을 검증한다.

### 심사 대응
- App Store 제출 메타데이터에서 ATS 예외 사유가 필요하지 않도록 HTTPS-only release 구성을 유지한다.
- `python3 client/scripts/verify_release_readiness.py`는 iOS ATS가 임의 로드나 insecure HTTP 예외를 허용하면 실패해야 한다.

---

## Android ProGuard / R8 규칙

### 현재 상태

ProGuard 규칙 파일이 없음 (`proguard-rules.pro` 미생성).

### 권장 규칙

`client/android/app/proguard-rules.pro` 파일 생성:

```proguard
# Flutter 리플렉션 보호
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Firebase
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**

# MethodChannel (네이티브 통신)
-keep class com.voicetextnote.app.** { *; }

# record 패키지
-keep class com.llfbandit.record.** { *; }

# permission_handler
-keep class com.baseflow.permissionhandler.** { *; }
```

### build.gradle 적용

```gradle
android {
    buildTypes {
        release {
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'),
                          'proguard-rules.pro'
            signingConfig signingConfigs.release
        }
    }
}
```
