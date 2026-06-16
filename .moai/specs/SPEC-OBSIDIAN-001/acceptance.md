# SPEC-OBSIDIAN-001: Acceptance Criteria

## 테스트 시나리오 (Given-When-Then)

### REQ-OBS-001: Vault 경로 설정

#### AC-001: 유효한 vault 경로 설정
- **Given** vault 경로 `/Users/test/MyVault`에 `.obsidian/` 폴더가 존재
- **When** `POST /api/v1/obsidian/config` with `vault_path: "/Users/test/MyVault"`
- **Then** 응답 200, `vault_valid: true`, `vault_name: "MyVault"`

#### AC-002: 무효한 vault 경로 거부
- **Given** 경로 `/tmp/random`에 `.obsidian/` 폴더가 없음
- **When** `POST /api/v1/obsidian/config` with `vault_path: "/tmp/random"`
- **Then** 응답 400, `error_code: INVALID_VAULT_PATH`

#### AC-003: 심볼릭 링크 거부
- **Given** `/Users/test/VaultLink`이 `/Users/test/RealVault`의 심볼릭 링크
- **When** `POST /api/v1/obsidian/config` with `vault_path: "/Users/test/VaultLink"`
- **Then** 응답 400, `error_code: SYMLINK_VAULT_DETECTED`

---

### REQ-OBS-002/003: 폴더/파일명 패턴

#### AC-004: 기본 폴더 패턴
- **Given** 설정 `folder_pattern: "Voice-to-TextNote/{{date}}"`, 회의 날짜 2026-06-16
- **When** 노트 생성
- **Then** 파일이 `{vault}/Voice-to-TextNote/2026-06-16/` 폴더에 생성됨

#### AC-005: 파일명 sanitization
- **Given** 회의 제목 `프로젝트/X 회의: 최종 검토!!`
- **When** 파일명 생성
- **Then** 결과: `프로젝트_X_회의_최종_검토.md` (특수문자 → `_`, 100자 이내)

#### AC-006: 빈 패턴 시 기본값
- **Given** `folder_pattern` 미설정
- **When** 노트 생성
- **Then** vault 루트에 파일 생성됨

---

### REQ-OBS-004/005: 노트 포맷

#### AC-007: YAML frontmatter 유효성
- **Given** 정상 회의 데이터
- **When** 노트 생성
- **Then** frontmatter가 유효한 YAML이고 `type`, `date`, `tags`, `source` 필드 포함

#### AC-008: 모든 섹션 포함
- **Given** minutes, summary, sentiment, tone 데이터가 모두 있는 회의
- **When** 노트 생성
- **Then** `## 📋 개요`, `## ✅ 액션 아이템`, `## 📌 주요 결정`, `## 📝 회의록`, `## 📊 감정 분석`, `## 🎵 톤 분석` 섹션 모두 존재

#### AC-009: 분석 데이터 없을 시 섹션 생략
- **Given** sentiment/tone 분석이 없는 회의
- **When** 노트 생성
- **Then** 감정 분석/톤 분석 섹션이 노트에서 제외됨

---

### REQ-OBS-006: 수동 Export

#### AC-010: 정상 수동 export
- **Given** meeting_id에 해당하는 회의 데이터가 존재, vault 설정 완료
- **When** `POST /api/v1/obsidian/export/{meeting_id}`
- **Then** 응답 200, `success: true`, `file_path`와 `obsidian_uri` 반환

#### AC-011: vault 미설정 시 export
- **Given** vault 설정이 없음
- **When** `POST /api/v1/obsidian/export/{meeting_id}`
- **Then** 응답 503, `error_code: OBSIDIAN_NOT_CONFIGURED`

#### AC-012: 존재하지 않는 meeting_id
- **Given** meeting_id `nonexistent-123`
- **When** `POST /api/v1/obsidian/export/nonexistent-123`
- **Then** 응답 404

---

### REQ-OBS-007: 자동 Export

#### AC-013: 파이프라인 완료 시 자동 export
- **Given** `auto_export: true`, vault 설정 완료
- **When** 파이프라인이 completed 상태 도달
- **Then** vault에 노트 파일이 자동 생성됨

#### AC-014: 자동 export 실패 시 파이프라인 영향 없음
- **Given** `auto_export: true`, vault 경로에 쓰기 권한 없음
- **When** 파이프라인 완료 → 자동 export 시도
- **Then** 자동 export 실패 로그 기록, 파이프라인은 정상 completed

#### AC-015: auto_export 비활성화
- **Given** `auto_export: false`
- **When** 파이프라인 완료
- **Then** 자동 export 시도 안 함

---

### REQ-OBS-008: Atomic Write

#### AC-016: atomic write 성공
- **Given** 충분한 디스크 공간
- **When** 노트 파일 생성
- **Then** vault에 완전한 파일만 존재 (부분 작성 파일 없음)

#### AC-017: 디스크 가득 참 처리
- **Given** 디스크 공간 부족
- **When** 노트 파일 생성 시도
- **Then** 임시 파일 정리됨, 에러 반환, vault에 손상 파일 없음

---

### REQ-OBS-009: Obsidian URI

#### AC-018: URI 생성
- **Given** vault name `MyVault`, 파일 경로 `Meetings/2026-06-16/note.md`
- **When** URI 생성
- **Then** `obsidian://open?vault=MyVault&file=Meetings%2F2026-06-16%2Fnote`

---

### REQ-OBS-013: 보안 — 경로 탐색 방지

#### AC-019: 경로 탐색 차단
- **Given** vault `/Users/test/MyVault`
- **When** 폴더 패턴 `../../etc`로 설정 시도
- **Then** 응답 400, `error_code: PATH_TRAVERSAL_DETECTED`

#### AC-020: 절대 경로 거부
- **Given** 폴더 패턴 `/etc/passwd`
- **When** 설정 시도
- **Then** 응답 400

---

### REQ-OBS-010/011: 커스터마이징

#### AC-021: 커스텀 태그 추가
- **Given** frontmatter_custom.additional_tags: `["work", "project-x"]`
- **When** 노트 생성
- **Then** frontmatter tags에 `voice-to-textnote`, `meetings`, `work`, `project-x` 모두 포함

---

### REQ-OBS-014: 오류 격리

#### AC-022: ObsidianService 예외 독립성
- **Given** 자동 export 중 예외 발생
- **When** summary_task 처리
- **Then** summary_task는 completed로 완료, Obsidian 오류는 별도 로그
