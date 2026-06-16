# SPEC-OBSIDIAN-001: Obsidian Vault 연계 — 회의록/요약 자동 기록

- **생성일**: 2026-06-16
- **상태**: Planned
- **우선순위**: High
- **담당**: Sisyphus (orchestration)
- **관련 SPEC**: SPEC-EXPORT-001 (PDF Export), SPEC-TMPL-001 (Templates), SPEC-SENTIMENT-001, SPEC-TONE-001
- **라이프사이클**: spec-anchored (구현과 함께 유지보수)

---

## 1. 개요

Voice-to-TextNote의 회의 처리 결과(회의록, AI 요약, 액션 아이템, 감정/톤 분석)를 사용자의 로컬 Obsidian vault에 자동으로 기록한다. 백엔드와 vault가 같은 머신에 있다는 점을 활용하여, 파일 시스템 직접 쓰기로 가장 견고한 통합을 제공한다.

### 핵심 가치

- **지식 베이스 구축**: 회의 내용이 Obsidian의 위키링크/태그/그래프에 자동 통합
- **마찰 없는 워크플로**: 파이프라인 완료 시 자동 기록, 별도 행동 불필요
- **양방향 연결**: iOS 앱에서 "Obsidian에서 열기"로 즉시 이동

---

## 2. 환경 (Environment)

- 백엔드(FastAPI + Celery)와 Obsidian vault가 동일 머신(Mac mini)에서 실행
- Obsidian은 vault 폴더의 파일 변경을 자동 감지 (외부 편집 허용)
- vault 경로는 사용자가 설정 (기본값 없음 — 명시적 설정 필수)
- 단일 sync backend만 사용 권장 (Obsidian Sync 또는 iCloud 중 하나, 병행 금지)

---

## 3. 가정 (Assumptions)

| ID | 가정 | 신뢰도 | 근거 |
|---|---|---|---|
| A-01 | 백엔드 프로세스가 vault 경로에 대한 파일 시스템 쓰기 권한을 가짐 | 높음 | 동일 머신, 동일 사용자 |
| A-02 | Obsidian이 실행 중이 아니어도 파일 쓰기는 성공함 | 높음 | vault는 로컬 폴더 |
| A-03 | Obsidian 재시작 시 외부 변경 사항이 자동 반영됨 | 높음 | 공식 문서 확인 |
| A-04 | 단일 writer(백엔드)만 파일에 쓰므로 동시성 충돌 위험 낮음 | 높음 | 사용자가 동일 노트를 동시 편집하지 않는 한 |
| A-05 | vault 경로가 심볼릭 링크가 아님 | 중간 | Obsidian 공식 비권장, 설정 시 검증 |

---

## 4. 요구사항 (Requirements)

### REQ-OBS-001: Vault 경로 설정 (Ubiquitous)

**The system shall** 항상 Obsidian vault 경로가 설정되어 있고 유효한 경우에만 노트 생성을 허용한다.

- vault 경로는 `.obsidian/` 폴더 존재 여부로 검증
- 심볼릭 링크 경로는 거부 (경고와 함께)
- 경로가 유효하지 않으면 자동 export를 건너뛰고 로그 기록

### REQ-OBS-002: 폴더 구조 패턴 (State-Driven)

**IF** 사용자가 폴더 패턴을 설정했으면, **THEN** 노트를 해당 패턴 경로에 생성한다.

- 기본 패턴: `Voice-to-TextNote/{{date}}` (예: `Voice-to-TextNote/2026-06-16`)
- 지원 변수: `{{date}}`, `{{year}}`, `{{month}}`, `{{title}}`, `{{type}}`
- 폴더가 없으면 자동 생성
- 패턴이 없으면 vault 루트에 생성

### REQ-OBS-003: 파일명 패턴 (State-Driven)

**IF** 사용자가 파일명 패턴을 설정했으면, **THEN** 해당 패턴으로 파일명을 생성한다.

- 기본 패턴: `{{date}}_{{title}}.md` (예: `2026-06-16_프로젝트_회의.md`)
- 지원 변수: `{{date}}`, `{{time}}`, `{{title}}`, `{{meeting_id}}`
- 파일명 sanitization: 특수문자 제거, 공백 → 언더스코어, 길이 제한(100자)
- 동일 파일명 존재 시 덮어쓰기 (설정 가능: overwrite vs skip)

### REQ-OBS-004: YAML Frontmatter (Event-Driven)

**WHEN** 노트가 생성되면, **THEN** YAML frontmatter를 포함한다.

필수 필드:
```yaml
type: meeting
date: YYYY-MM-DD
time: HH:MM
duration_seconds: integer
title: string
participants:
  - "[[Speaker 1]]"
  - "[[Speaker 2]]"
tags:
  - voice-to-textnote
  - meetings
source: voice-to-textnote
meeting_id: string
```

선택 필드 (분석 완료 시):
```yaml
sentiment: positive|neutral|negative
overall_emotion: string
overall_tone: string
action_item_count: integer
```

### REQ-OBS-005: 노트 본문 구조 (Event-Driven)

**WHEN** 노트가 생성되면, **THEN** 다음 섹션을 포함한다.

1. **헤더**: `# {회의 제목}`
2. **개요** (`## 📋 개요`): AI 요약 텍스트
3. **액션 아이템** (`## ✅ 액션 아이템`): 체크박스 목록
4. **주요 결정** (`## 📌 주요 결정`): 불릿 목록
5. **다음 단계** (`## ➡️ 다음 단계`): 불릿 목록
6. **회의록** (`## 📝 회의록`): 화자별 타임스탬프 발화
7. **감정 분석** (`## 📊 감정 분석`): 전체 감정, 화자별 분포 (선택)
8. **톤 분석** (`## 🎵 톤 분석`): 전체 톤, 화자별 톤 (선택)
9. **링크** (`## 🔗 링크`): 위키링크 (예: `[[{{date}}]]`, `[[Meetings]]`)

### REQ-OBS-006: 수동 Export (Event-Driven)

**WHEN** 클라이언트가 `POST /api/v1/obsidian/export/{meeting_id}`를 호출하면, **THEN** 회의 내용을 vault에 .md 파일로 생성하고 파일 경로를 반환한다.

- meeting_id가 존재하지 않으면 404
- vault 설정이 없으면 503 (설정 필요 안내)
- 기존 파일 존재 시 설정에 따라 덮어쓰기 또는 건너뛰기

### REQ-OBS-007: 자동 Export (Event-Driven)

**WHEN** 파이프라인이 completed 상태가 되면, **THEN** 자동으로 vault에 노트를 생성한다.

- 설정 토글: `obsidian_auto_export` (기본값: false)
- 파이프라인 실패 시 자동 export 안 함
- 자동 export 실패 시 파이프라인 상태에 영향 주지 않음 (독립 실패)
- summary_task, sentiment_task, tone_task 완료 대기 후 통합 노트 생성

### REQ-OBS-008: Atomic File Write (Ubiquitous)

**The system shall** 항상 atomic write 패턴으로 파일을 생성한다.

- 임시 파일 작성 → fsync → rename (원자적 교체)
- 부분 작성된 파일이 vault에 노출되지 않음
- 디스크 가득 참 등 실패 시 임시 파일 정리

### REQ-OBS-009: Obsidian URI 통합 (Optional)

**Where possible**, 클라이언트에 "Obsidian에서 열기" 버튼을 제공한다.

- URI 형식: `obsidian://open?vault={vault_name}&file={encoded_path}`
- vault 이름은 vault 폴더의 basename
- 파일 경로는 `.md` 확장자 제거 후 URL 인코딩
- URI 실행 실패 시 (Obsidian 미설치) 사용자 안내

### REQ-OBS-010: Frontmatter 커스터마이징 (Optional)

**Where possible**, 사용자가 frontmatter 필드와 값을 커스터마이징할 수 있다.

- 추가 태그, 커스텀 필드, 별칭(alias) 정의 가능
- 템플릿 기반 frontmatter (변수 치환)
- 설정 UI에서 관리

### REQ-OBS-011: 노트 템플릿 선택 (Optional)

**Where possible**, 사용자가 노트 본문 구조를 템플릿으로 선택할 수 있다.

- 기본 템플릿: 표준 회의록 (REQ-OBS-005 구조)
- 커스텀 템플릿: Markdown 파일 업로드, 변수 치환 (`{{summary}}`, `{{action_items}}` 등)
- SPEC-TMPL-001 템플릿 시스템 재활용

### REQ-OBS-012: 설정 관리 (Event-Driven)

**WHEN** 클라이언트가 `POST /api/v1/obsidian/config`를 호출하면, **THEN** vault 설정을 저장하고 검증한다.

- vault 경로 검증 (`.obsidian/` 폴더 존재)
- 폴더 패턴, 파일명 패턴, frontmatter 커스텀 저장
- 자동 export 토글
- 기존 파일 충돌 정책 (overwrite / skip)
- 설정은 DB에 영구 저장 (팀 단위 또는 사용자 단위)

### REQ-OBS-013: 보안 — 경로 탐색 방지 (Unwanted)

**The system shall not** vault 경로 외부로 파일을 작성할 수 있다.

- 모든 파일 경로는 vault 루트 기준 상대 경로로 정규화
- `../` 경로 탐색 시도 감지 및 차단
- 절대 경로 입력 거부 (vault 내부에서만 허용)
- 파일명 sanitization으로 OS 명령어 주입 방지

### REQ-OBS-014: 오류 격리 (Unwanted)

**The system shall not** Obsidian 통합 실패가 핵심 파이프라인(STT/DIA/minutes/summary)에 영향을 준다.

- 자동 export 실패 시 로그만 기록, 파이프라인은 계속 completed
- ObsidianService 예외는 독립적으로 처리
- vault 미설정 시 자동 export 조용히 건너뜀 (경고 로그)

---

## 5. 데이터 플로우

```
파이프라인 완료 (summary + sentiment + tone)
         ↓
ObsidianService.export_meeting(meeting_id)
         ↓
    [설정 로드] ← DB obsidian_config
         ↓ (vault 미설정? → 종료, 로그)
    [데이터 수집] ← minutes result + summary result + sentiment + tone
         ↓
    [Markdown 조합] ← frontmatter + sections + wikilinks
         ↓
    [경로 계산] ← folder_pattern + filename_pattern
         ↓
    [Atomic Write] ← temp file → fsync → rename
         ↓
    [URI 생성] ← obsidian://open?vault=...&file=...
         ↓
    [결과 반환] ← {success, file_path, obsidian_uri}
```

---

## 6. API 엔드포인트

### 6.1 설정 API

```
POST /api/v1/obsidian/config
GET  /api/v1/obsidian/config
PUT  /api/v1/obsidian/config  (전체 교체)
```

Request Body (POST/PUT):
```json
{
  "vault_path": "/Users/ibkim/MyVault",
  "folder_pattern": "Meetings/{{year}}/{{month}}",
  "filename_pattern": "{{date}}_{{title}}",
  "auto_export": true,
  "conflict_policy": "overwrite",
  "frontmatter_custom": {
    "additional_tags": ["work", "project-x"],
    "custom_fields": { "team": "engineering" }
  },
  "note_template_id": null
}
```

Response:
```json
{
  "vault_path": "/Users/ibkim/MyVault",
  "vault_name": "MyVault",
  "vault_valid": true,
  "folder_pattern": "Meetings/{{year}}/{{month}}",
  "filename_pattern": "{{date}}_{{title}}",
  "auto_export": true,
  "conflict_policy": "overwrite"
}
```

### 6.2 Export API

```
POST /api/v1/obsidian/export/{meeting_id}
```

Response (200):
```json
{
  "success": true,
  "file_path": "Meetings/2026/06/2026-06-16_프로젝트_회의.md",
  "obsidian_uri": "obsidian://open?vault=MyVault&file=Meetings%2F2026%2F06%2F2026-06-16_%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8_%ED%9A%8C%EC%9D%98"
}
```

Response (503 — vault 미설정):
```json
{
  "error_code": "OBSIDIAN_NOT_CONFIGURED",
  "message": "Obsidian vault 경로가 설정되지 않았습니다"
}
```

### 6.3 Vault 검증 API

```
POST /api/v1/obsidian/validate?vault_path=/Users/ibkim/MyVault
```

Response:
```json
{
  "valid": true,
  "vault_name": "MyVault",
  "obsidian_folder_exists": true,
  "writable": true,
  "is_symlink": false
}
```

---

## 7. 기술 스택

| 계층 | 기술 | 비고 |
|---|---|---|
| Backend service | Python `pathlib`, `aiofiles`, `yaml` | 새 패키지: `pyyaml` (이미 설치 가능성 높음) |
| Atomic write | `tempfile.NamedTemporaryFile` + `os.replace()` | Python 표준 라이브러리 |
| DB 저장 | SQLAlchemy `ObsidianConfig` 모델 | 팀/사용자 단위 설정 |
| Client UI | Flutter `url_launcher` | `obsidian://` URI 실행 |
| Markdown 생성 | 기존 `minutes_formatter.py` 패턴 확장 | 재사용 |

---

## 8. 클라이언트 UI 변경

### 결과 화면 — 새 버튼

1. **"Obsidian에 저장"** 버튼 (내보내기 메뉴 확장)
   - 기존 PDF/DOCX/Markdown 내보내기 옆에 추가
   - 탭: 수동 export 트리거

2. **"Obsidian에서 열기"** 버튼 (노트 생성 후 표시)
   - `obsidian://` URI 실행
   - 실패 시 "Obsidian이 설치되어 있는지 확인하세요" 안내

### 설정 화면 — Obsidian 섹션

- Vault 경로 입력 (서버 로컬 경로)
- "검증" 버튼
- 폴더/파일명 패턴 입력
- 자동 export 토글
- Frontmatter 커스터마이징 (추가 태그, 커스텀 필드)

---

## 9. 제외 범위 (Out of Scope)

- Local REST API 플러그인 통합 (향후 고급 기능용)
- Obsidian Sync / iCloud 충돌 해결 (사용자 환경 책임)
- 실시간 양방향 동기화 (단방향 export만)
- Obsidian 플러그인 개발 (별도 프로젝트)
- vault 내 기존 노트 수정/삭제 (생성만)
- iOS에서 vault 직접 접근 (서버 경유만)

---

## 10. 성공 기준

| 기준 | 측정 방법 | 목표 |
|---|---|---|
| 자동 export 성공률 | 자동 export 시도 중 성공 비율 | ≥ 99% |
| 수동 export 응답 시간 | POST /obsidian/export 응답 시간 | P50 < 2초, P95 < 5초 |
| 노트 포맷 정확도 | 생성된 노트의 frontmatter/섹션 검증 | 100% 유효 YAML |
| 경로 탐색 방지 | `../` 시도 차단 | 100% 차단 |
| 파이프라인 독립성 | Obsidian 실패 시 파이프라인 영향 | 0건 영향 |

---

## 11. 테스트 시나리오

### Normal Cases

1. **정상 자동 export**: 파이프라인 완료 → vault에 노트 생성 → Obsidian에서 확인
2. **정상 수동 export**: 결과 화면 "Obsidian에 저장" → 노트 생성 → "Obsidian에서 열기"
3. **vault 경로 설정**: 설정 입력 → 검증 → 저장 → export 가능

### Error Cases

4. **vault 미설정**: 자동 export 시도 → 조용히 건너뜀 (로그만)
5. **vault 경로 무효**: 수동 export → 503 에러
6. **디스크 가득 참**: atomic write 실패 → 임시 파일 정리 → 에러 반환
7. **기존 파일 충돌**: conflict_policy=skip → 건너뜀, conflict_policy=overwrite → 덮어쓰기

### Security Cases

8. **경로 탐색 시도**: `../../etc/passwd` → 400 Bad Request
9. **파일명 주입**: `; rm -rf /` → sanitization 후 안전한 파일명
10. **심볼릭 링크 vault**: 설정 검증 시 거부

### Edge Cases

11. **긴 회의 제목**: 100자 초과 → truncation
12. **빈 회의록**: segments 없음 → 최소 frontmatter만 생성
13. **동시 export 요청**: 같은 meeting_id → 두 번째는 대기 또는 skip

---

## 12. 마일스톤

| 단계 | 내용 | 예상 시간 |
|---|---|---|
| M1 | Backend: ObsidianConfig DB 모델 + 설정 API | 1h |
| M2 | Backend: ObsidianService (경로 계산, atomic write, markdown 조합) | 2h |
| M3 | Backend: Export 엔드포인트 + 자동 트리거 통합 | 1h |
| M4 | Backend: Vault 검증 + 경로 탐색 방지 | 1h |
| M5 | Client: "Obsidian에 저장" + "Obsidian에서 열기" UI | 1h |
| M6 | Client: 설정 화면 Obsidian 섹션 | 1h |
| M7 | 통합 테스트 + 문서화 | 1h |

---

## 13. 리스크

| 리스크 | 확률 | 영향 | 완화책 |
|---|---|---|---|
| Obsidian Sync가 외부 쓰기 충돌 | 중간 | 노트 손상 가능 | 단일 sync backend 권장 문서화, atomic write |
| vault 경로 변경 시 기존 노트 단절 | 낮음 | 검색 불가 | 경로 변경 시 마이그레이션 안내 |
| frontmatter 변수 치환 실패 | 낮음 | 잘못된 노트 | 폴백 기본값, 검증 로직 |
| Obsidian이 실행 중이 아님 | 높음 | 실시간 미반영 | 재시작 시 자동 감지 문서화 |
