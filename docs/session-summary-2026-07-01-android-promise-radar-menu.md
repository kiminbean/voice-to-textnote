# 2026-07-01 Android Promise Radar Menu Follow-up

## Context

Android `Redmi Note 9 Pro`에서 결과 화면의 `약속 레이더` 메뉴가 보이지 않는 문제가 보고됐다.

## Root Cause

기기에 설치된 APK가 오래된 release 빌드였다. UIAutomator dump에서 결과 화면 탭이 `11개`로 표시됐고 `약속 레이더` 탭이 없었다. 현재 코드의 `ResultScreen`은 `약속 레이더`를 포함해 탭 `12개`를 구성한다.

## Fix

Android 기기에 최신 private staging release를 다시 설치했다.

```bash
cd client
flutter run --release --no-pub --no-resident \
  -d 76aadc20 \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

## Evidence

- Device: `Redmi Note 9 Pro`, Android 12 API 31, ADB serial `76aadc20`.
- Installed package: `com.voicetextnote.app`, `versionName=1.0.0`, `lastUpdateTime=2026-07-01 15:39:18`.
- Built APK guard: `libapp.so` contains `http://100.69.69.119:8000/api/v1`.
- UIAutomator after reinstall: `약속 레이더\n탭 12개 중 4번째`.
- Screenshot evidence: `/tmp/vtt-android-promise-radar.png` showed the `약속 레이더` tab selected.

## Recurrence Guard

- Do not diagnose a missing Promise Radar tab as a backend/API problem until the installed Android APK timestamp is confirmed current.
- Private staging release builds must always include both `--dart-define=ENV=staging` and `--dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1`.
- If the tab list shows `탭 11개`, the device is running a stale build. Reinstall the Android staging release and verify the tab list shows `탭 12개`.
- `adb shell input tap` can be blocked on MIUI by `INJECT_EVENTS` restrictions; use screenshots and UIAutomator dumps for non-invasive verification.
