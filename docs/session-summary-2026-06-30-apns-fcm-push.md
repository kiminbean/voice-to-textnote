# Session Summary: APNs / FCM Real Push Verification

Date: 2026-06-30

## Summary

iPhone 실기기 APNs registration, Firebase Messaging FCM token 발급, 백엔드 device token 등록, 원격 백엔드 Firebase Admin SDK 실제 전송까지 검증했다.

## Current Baseline

- Firebase project: `voice-to-textnote`
- Firebase CLI account: `kiminbean@gmail.com`
- iOS bundle ID: `com.voicetextnote.app`
- iPhone device ID: `00008150-000239020C08401C`
- iPhone CoreDevice ID: `C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA`
- Remote backend host: `100.69.69.119`
- Remote backend repo: `/Users/ibkim/Projects/voice-to-textnote`
- App API base for device testing: `http://100.69.69.119:8000/api/v1`
- Verified commit: `25dce3d`

## Client Changes

- `client/ios/Runner.xcodeproj/project.pbxproj`
  - `Runner/Runner.entitlements` is wired into code signing.
  - Signing remains automatic.
- `client/ios/Runner/AppDelegate.swift`
  - Calls `application.registerForRemoteNotifications()`.
  - Bridges APNs device token into Firebase Messaging with `Messaging.messaging().apnsToken`.
  - Logs APNs registration failure.
- `client/lib/services/push_notification_service.dart`
  - Waits briefly for APNs token before topic subscription and FCM token retrieval.
- `client/lib/main.dart`
  - Initializes notifications after auth/guest state becomes available, avoiding token registration races.
- `client/lib/services/device_api.dart`
  - Sends real platform value, currently `ios` on iPhone.
- `client/test/services/device_api_test.dart`
  - Updated expected platform to `ios`.

## Remote Backend Configuration

Firebase Admin service account JSON is stored outside the repository:

```text
/Users/ibkim/secure/voice-to-textnote/firebase-adminsdk-fbsvc.json
```

Remote `.env` must include:

```env
FIREBASE_CREDENTIALS_PATH=/Users/ibkim/secure/voice-to-textnote/firebase-adminsdk-fbsvc.json
```

Do not add this key to the current remote `.env`:

```env
FIREBASE_PROJECT_ID=voice-to-textnote
```

Reason: the current backend `Settings` model forbids unknown env keys, so `FIREBASE_PROJECT_ID` causes startup failure with `extra_forbidden`.

The local `.env` was synced to the remote backend PC while preserving `FIREBASE_CREDENTIALS_PATH`. Remote backup:

```text
.env.before-local-sync-20260630-011804
```

## Database Repair

The remote SQLite DB had Alembic head recorded but was missing `device_tokens.device_id`.

Backup created:

```text
voice_to_textnote.db.before-device-id-fix-20260630-005711
```

Manual repair applied:

```sql
ALTER TABLE device_tokens ADD COLUMN device_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS ix_device_tokens_device_id ON device_tokens (device_id);
CREATE INDEX IF NOT EXISTS ix_device_tokens_user_device_id ON device_tokens (user_id, device_id);
```

## Verification

Flutter checks:

```bash
cd client
flutter analyze --no-pub
flutter test --no-pub \
  test/services/device_api_test.dart \
  test/providers/notification_provider_test.dart \
  test/services/push_notification_service_test.dart
```

Result:

```text
No issues found
31 tests passed
```

iPhone profile run:

```bash
cd client
flutter run --profile --no-pub \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

Observed app/backend evidence:

- `Firebase 초기화 성공`
- `FCM 권한 상태: AuthorizationStatus.authorized`
- `APNs 토큰 준비 완료`
- `토픽 구독 완료: all`
- `/api/v1/devices/register` returned 201
- latest remote DB token row had `platform=ios`, `is_active=1`, FCM token length `142`

Remote health after restart:

```text
api=healthy
redis=healthy
celery_workers.active_workers=1
ffmpeg=available
```

Firebase Admin actual mode:

```text
mock_mode False
```

Actual FCM/APNs send evidence:

```text
send_ok True
message_id projects/voice-to-textnote/messages/1782749586143713
```

## Git

Committed and pushed:

```text
25dce3d Enable real iOS push registration
```

Remote backend PC was fast-forwarded to the same commit.

## Operational Lessons

- iOS visible banners may not appear while the app is foregrounded. For visible notification UI verification, put the app in background or lock the device before sending.
- Server-side FCM acceptance is verified by Firebase Admin returning a message id.
- Keep service account JSON outside the repository and do not print or commit its contents.
- When syncing `.env` from local to remote, preserve remote-only operational keys such as `FIREBASE_CREDENTIALS_PATH`.
- Flutter commands can delete or modify generated iOS lock files such as `client/ios/Runner.xcworkspace/xcshareddata/swiftpm/Package.resolved`; restore unrelated generated churn before committing.
