# ATS / ProGuard 설정 문서 (T-018)

**SPEC-MOBILE-004 | 작성일: 2026-06-13**

---

## iOS App Transport Security (ATS)

### 현재 상태

`Info.plist`는 release 기준으로 임의 HTTP 로드를 차단한다. 현재 private
staging 실기기 release 검증은 unresolved production API 대신 Tailscale 백엔드
`100.69.69.119`를 사용하므로, iOS ATS와 Android release/profile network security에
해당 IP 하나만 좁게 허용한다.

```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <false/>
    <key>NSExceptionDomains</key>
    <dict>
        <key>100.69.69.119</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <true/>
            <key>NSIncludesSubdomains</key>
            <false/>
        </dict>
    </dict>
</dict>
```

### 프로덕션 정책

App Store/Play 제출용 production 빌드는 HTTPS-only 백엔드가 준비된 뒤 HTTP 예외를
제거해야 한다. 현재 실기기 staging release 검증에서는 `100.69.69.119`만 예외로
허용하고, 그 외 모든 HTTP 도메인은 실패해야 한다. 새 staging HTTP host가 필요하면
플랫폼 보안 설정, `verify_release_readiness.py`, 회귀 테스트, release 문서를 같은
커밋에서 함께 갱신한다.

### 심사 대응
- App Store 제출 메타데이터에서 ATS 예외 사유가 필요하지 않도록 제출 전 production
  빌드는 HTTPS-only 구성을 사용한다.
- `python3 client/scripts/verify_release_readiness.py`는 iOS ATS가 임의 로드나
  `100.69.69.119` 외 insecure HTTP 예외를 허용하면 실패해야 한다.

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
