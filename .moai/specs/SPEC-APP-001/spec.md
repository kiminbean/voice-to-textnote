---
id: SPEC-APP-001
version: "1.0.0"
status: completed
created: 2026-03-15
updated: 2026-03-15
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-APP-001: Flutter 클라이언트 MVP - 오디오 녹음 및 회의록 파이프라인 연동

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-15 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 프레임워크 | Flutter 3.22+ / Dart 3.4+ |
| 상태관리 | Riverpod 2.5+ (flutter_riverpod) |
| HTTP 클라이언트 | Dio 5.4+ |
| 오디오 녹음 | record 5.1+ |
| 라우팅 | go_router 14.0+ |
| 대상 플랫폼 | Web (Chrome), macOS (우선), iOS/Android (향후) |
| 백엔드 | FastAPI (localhost:8000) |

---

## 2. 가정 (Assumptions)

- 백엔드 서버(FastAPI + Celery + Redis)가 localhost:8000에서 실행 중이다.
- 사용자는 마이크 접근 권한을 허용한다.
- 녹음 파일 형식은 WAV (16bit, 모노)로 백엔드 전처리 호환.
- 첫 MVP는 Web + macOS 타겟이며, iOS/Android는 향후 SPEC에서 다룬다.
- 다국어(i18n)는 향후 SPEC에서 다룬다. 초기 UI는 한국어 하드코딩.
- 인증(Auth)은 향후 SPEC에서 다룬다. 초기에는 인증 없이 동작.

---

## 3. 요구사항 (Requirements)

### 모듈 1: 프로젝트 구조 및 설정

**[REQ-APP-001] [유비쿼터스]** 프로젝트는 항상 `client/` 디렉토리에 Flutter 프로젝트로 생성해야 한다. 패키지명: `voice_to_textnote`.

**[REQ-APP-002] [유비쿼터스]** 프로젝트는 항상 다음 의존성을 포함해야 한다: flutter_riverpod, dio, go_router, record, intl, freezed_annotation, json_annotation.

**[REQ-APP-003] [유비쿼터스]** 앱 설정(API 서버 URL 등)은 항상 `AppConfig` 클래스에서 중앙 관리해야 한다. 기본 API URL: `http://localhost:8000/api/v1`.

### 모듈 2: API 서비스 레이어

**[REQ-APP-004] [유비쿼터스]** ApiService는 항상 Dio 인스턴스를 사용하여 백엔드 API와 통신해야 한다. 모든 HTTP 호출에 타임아웃(30초), 에러 인터셉터를 적용한다.

**[REQ-APP-005] [유비쿼터스]** TranscriptionApiService는 항상 다음 엔드포인트를 지원해야 한다: POST /transcriptions (파일 업로드), GET /transcriptions/{id}/status, GET /transcriptions/{id}, DELETE /transcriptions/{id}.

**[REQ-APP-006] [유비쿼터스]** DiarizationApiService는 항상 다음 엔드포인트를 지원해야 한다: POST /diarizations, GET /diarizations/{id}/status, GET /diarizations/{id}, DELETE /diarizations/{id}.

**[REQ-APP-007] [유비쿼터스]** MinutesApiService는 항상 다음 엔드포인트를 지원해야 한다: POST /minutes, GET /minutes/{id}/status, GET /minutes/{id}, DELETE /minutes/{id}.

**[REQ-APP-008] [유비쿼터스]** SummaryApiService는 항상 다음 엔드포인트를 지원해야 한다: POST /summaries, GET /summaries/{id}/status, GET /summaries/{id}, DELETE /summaries/{id}.

**[REQ-APP-009] [유비쿼터스]** HealthApiService는 항상 GET /health 엔드포인트를 지원해야 한다. 서버 연결 상태를 확인한다.

### 모듈 3: 상태 관리 (Riverpod)

**[REQ-APP-010] [유비쿼터스]** RecordingNotifier는 항상 녹음 상태(idle/recording/paused/stopped)를 관리하고 녹음 시간(초)을 추적해야 한다.

**[REQ-APP-011] [유비쿼터스]** PipelineNotifier는 항상 전체 파이프라인 상태를 관리해야 한다: upload → transcription → diarization → minutes → summary. 각 단계의 진행률을 추적한다.

**[REQ-APP-012] [이벤트 기반]** WHEN 파이프라인 단계가 완료될 때 THEN PipelineNotifier는 자동으로 다음 단계를 시작해야 한다. 실패 시 해당 단계에서 멈추고 에러를 표시한다.

**[REQ-APP-013] [유비쿼터스]** MeetingListNotifier는 항상 로컬에 저장된 회의 목록을 관리해야 한다. 각 회의에는 id, title, date, status, duration 정보가 포함된다.

### 모듈 4: UI 화면

**[REQ-APP-014] [유비쿼터스]** HomeScreen은 항상 회의 목록을 표시해야 한다. 각 카드에는 제목, 날짜, 상태(녹음중/처리중/완료), 재생 시간이 표시된다.

**[REQ-APP-015] [유비쿼터스]** RecordingScreen은 항상 녹음 버튼(시작/중지), 녹음 시간 타이머, 오디오 파형 시각화를 포함해야 한다.

**[REQ-APP-016] [유비쿼터스]** ProcessingScreen은 항상 파이프라인 진행 상태를 단계별로 표시해야 한다: 업로드 → STT → 화자분리 → 회의록 → AI요약. 각 단계의 진행률(%)을 표시한다.

**[REQ-APP-017] [유비쿼터스]** ResultScreen은 항상 완료된 회의의 결과를 표시해야 한다: 화자별 회의록, AI 요약문, 액션 아이템 목록.

**[REQ-APP-018] [원치 않는 행동]** 시스템은 백엔드 서버 연결 실패 시 앱을 중단하지 않아야 한다. 연결 실패 메시지를 표시하고 재시도 옵션을 제공해야 한다.

### 모듈 5: 오디오 녹음

**[REQ-APP-019] [유비쿼터스]** AudioRecorder는 항상 record 패키지를 사용하여 마이크 입력을 WAV 형식으로 녹음해야 한다.

**[REQ-APP-020] [이벤트 기반]** WHEN 녹음이 완료(stop) 될 때 THEN 시스템은 녹음 파일을 자동으로 백엔드에 업로드하고 파이프라인을 시작해야 한다.

### 모듈 6: 라우팅

**[REQ-APP-021] [유비쿼터스]** 앱은 항상 go_router를 사용하여 다음 경로를 지원해야 한다: / (홈), /recording (녹음), /processing/:id (처리중), /result/:id (결과).

---

## 4. 비기능 요구사항 (Non-Functional Requirements)

| 항목 | 목표값 |
|------|--------|
| 앱 시작 시간 | < 2초 (릴리즈 빌드) |
| 녹음 시작 지연 | < 500ms |
| UI 반응 속도 | 60fps 유지 |
| 폴링 주기 | 2초 (파이프라인 상태 조회) |

---

## 5. 기술 제약 조건 (Technical Constraints)

- **Flutter 3.22+**: Dart 3.4+ 필수 (최신 타입 시스템).
- **Web + macOS**: 초기 MVP 대상 플랫폼.
- **마이크 권한**: macOS에서 마이크 entitlement 설정 필수.
- **CORS**: 백엔드 FastAPI에서 CORS 허용 필수 (이미 설정됨).

---

## 6. 의존성 (Dependencies)

| 패키지 | 버전 | 용도 |
|--------|------|------|
| flutter_riverpod | >= 2.5.0 | 상태 관리 |
| dio | >= 5.4.0 | HTTP 클라이언트 |
| go_router | >= 14.0.0 | 라우팅 |
| record | >= 5.1.0 | 오디오 녹음 |
| intl | >= 0.19.0 | 날짜/시간 포맷 |
| freezed_annotation | >= 2.4.0 | 불변 데이터 모델 |
| json_annotation | >= 4.9.0 | JSON 직렬화 |

---

## 7. 연결된 SPEC (Related SPECs)

| SPEC ID | 관계 | 설명 |
|---------|------|------|
| SPEC-STT-001 | API 소비 | POST /transcriptions 호출 |
| SPEC-DIA-001 | API 소비 | POST /diarizations 호출 |
| SPEC-MIN-001 | API 소비 | POST /minutes 호출 |
| SPEC-SUM-001 | API 소비 | POST /summaries 호출 |

---

*SPEC ID: SPEC-APP-001*
*생성일: 2026-03-15*
*상태: completed*

---

## 9. 구현 노트 (Implementation Notes)

- **구현 일자**: 2026-03-15
- **개발 방법론**: TDD
- **테스트 결과**: 37 Flutter tests passed, flutter analyze 0 issues
- **커밋**: 8e56e16 (main)
- 신규 파일 30+ 생성 (lib/ + test/ + config)
- freezed/json_serializable 대신 수동 직렬화 적용 (Dart SDK 호환성)
- macOS 마이크 entitlement 설정 완료
