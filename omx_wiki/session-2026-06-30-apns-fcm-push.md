# 2026-06-30 APNs / FCM Real Push Verification

## What Changed

- iOS APNs registration now runs during app startup.
- `AppDelegate.swift` bridges the APNs device token into Firebase Messaging.
- Flutter waits briefly for APNs token availability before requesting FCM token.
- Notification initialization now waits for authenticated or guest auth state.
- Backend device registration now sends `platform=ios` from iPhone.

## Verified Environment

- iPhone: `00008150-000239020C08401C`
- CoreDevice: `C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA`
- Remote backend: `100.69.69.119`
- Remote repo: `/Users/ibkim/Projects/voice-to-textnote`
- API base: `http://100.69.69.119:8000/api/v1`
- Commit: `25dce3d`

## Backend Firebase Admin

Remote `.env` must keep:

```env
FIREBASE_CREDENTIALS_PATH=/Users/ibkim/secure/voice-to-textnote/firebase-adminsdk-fbsvc.json
```

Do not add:

```env
FIREBASE_PROJECT_ID=voice-to-textnote
```

The current Settings model rejects that key and the backend will fail to start.

## Evidence

- Backend health: API, Redis, Celery, ffmpeg healthy.
- Celery workers: one active worker.
- Firebase Admin: `mock_mode False`.
- iPhone logs: `APNs 토큰 준비 완료`, `토픽 구독 완료: all`.
- Backend device registration: `/api/v1/devices/register` 201.
- Actual FCM/APNs send: `send_ok True`.
- Firebase message id: `projects/voice-to-textnote/messages/1782749586143713`.

## Follow-up Rules

- Preserve `FIREBASE_CREDENTIALS_PATH` when syncing local `.env` to the remote backend PC.
- Keep Firebase service account JSON outside the repo and never print the contents.
- For visible iOS notification banners, background or lock the app before sending; foreground delivery can succeed without a system banner.
- Restore unrelated Flutter-generated lockfile churn before committing.

## Canonical Docs

- `docs/session-summary-2026-06-30-apns-fcm-push.md`
- `docs/google-auth-ios-runbook.md`
- `docs/firebase-setup-guide.md`
- `docs/e2e-device-checklist.md`
- `docs/release-procedure.md`
