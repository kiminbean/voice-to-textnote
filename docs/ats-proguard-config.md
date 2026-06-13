# ATS / ProGuard 설정 문서 (T-018)

**SPEC-MOBILE-004 | 작성일: 2026-06-13**

---

## iOS App Transport Security (ATS)

### 현재 상태

`Info.plist`에서 `NSAllowsArbitraryLoads: true`로 설정되어 있음.

```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
</dict>
```

### 프로덕션 권장 설정

로컬 서버(Tailscale IP, HTTP) 통신을 위해 예외 도메인 사용을 권장:

```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
    <key>NSExceptionDomains</key>
    <dict>
        <key>100.x.x.x</key>  <!-- Tailscale IP -->
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <true/>
            <key>NSIncludesSubdomains</key>
            <true/>
        </dict>
    </dict>
</dict>
```

> 주의: `NSAllowsArbitraryLoads: true`는 App Store 심사 시 메타데이터에서 사유를 요구함.
> 프로덕션 빌드에서는 `NSAllowsLocalNetworking` + `NSExceptionDomains` 조합으로 전환 권장.

### 심사 대응
- App Store 심사 시 "ATS Configuration" 항목에서 HTTP 통신 사유 작성:
  - "로컬 네트워크의 자체 호스팅 서버와 통신하기 위해 HTTP를 사용합니다."

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
