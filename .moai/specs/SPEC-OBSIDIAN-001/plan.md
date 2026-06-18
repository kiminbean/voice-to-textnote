# SPEC-OBSIDIAN-001: Implementation Plan

## 아키텍처 결정

### 통합 방식: Direct File Write (3계층 하이브리드)
1. **Primary**: Direct file write — vault 폴더에 .md 파일 atomic write
2. **Secondary**: Obsidian URI — iOS 클라이언트 "Obsidian에서 열기"
3. **Tertiary**: (향후) Local REST API — 실시간 patch/검색

### 기술 선택 근거
- 백엔드와 vault가 동일 머신 → 파일 시스템 직접 접근 가능
- Python 표준 라이브러리만 사용 (`pathlib`, `tempfile`, `os.replace`)
- 추가 패키지 의존성 최소화

---

## 파일 변경 계획

### Backend (Python)

#### 신규 파일
1. `backend/services/obsidian_service.py` — 핵심 서비스 (경로 계산, markdown 조합, atomic write)
2. `backend/app/api/v1/integrations/obsidian.py` — API 엔드포인트 (config, export, validate)
3. `backend/schemas/obsidian.py` — Pydantic 스키마 (설정, 응답)
4. `backend/db/obsidian_models.py` — ObsidianConfig DB 모델

#### 수정 파일
5. `backend/app/config.py` — obsidian 기본 설정 추가 (vault_path, auto_export 등)
6. `backend/app/api/v1/registry.py` — obsidian 라우터 등록
7. `backend/workers/tasks/summary_task.py` — 파이프라인 완료 후 자동 export 트리거

### Client (Flutter/Dart)

#### 신규 파일
8. `client/lib/services/obsidian_api.dart` — Obsidian API 클라이언트
9. `client/lib/providers/obsidian_provider.dart` — 설정 상태 관리

#### 수정 파일
10. `client/lib/screens/result_screen.dart` — "Obsidian에 저장" / "Obsidian에서 열기" 버튼
11. `client/lib/screens/settings_screen.dart` (또는 신규) — Obsidian 설정 UI

---

## 마일스톤별 상세 계획

### M1: DB 모델 + 설정 API (1h)
- `ObsidianConfig` 모델: vault_path, folder_pattern, filename_pattern, auto_export, conflict_policy, frontmatter_custom, note_template_id
- POST/GET/PUT `/api/v1/obsidian/config`
- POST `/api/v1/obsidian/validate` — vault 경로 검증

### M2: ObsidianService (2h)
- `validate_vault(path)`: .obsidian 폴더 존재, 쓰기 권한, 심볼릭 링크 확인
- `compute_path(config, meeting)`: 폴더/파일명 패턴 변수 치환
- `build_frontmatter(meeting, summary, sentiment, tone)`: YAML 생성
- `build_note_body(meeting, minutes, summary, sentiment, tone)`: 섹션별 markdown
- `atomic_write(path, content)`: tempfile → fsync → rename
- `sanitize_filename(name)`: 특수문자 제거, 길이 제한

### M3: Export 엔드포인트 + 자동 트리거 (1h)
- POST `/api/v1/obsidian/export/{meeting_id}`
- summary_task 완료 시 자동 export 호출 (설정 시)

### M4: 보안 — 경로 탐색 방지 (1h)
- `_resolve_safe_path(vault_root, relative_path)`: 정규화 후 vault 내부 검증
- `../` 감지, 절대 경로 거부

### M5: Client UI — 결과 화면 (1h)
- "Obsidian에 저장" 버튼 (내보내기 메뉴)
- "Obsidian에서 열기" 버튼 (obsidian:// URI)

### M6: Client UI — 설정 화면 (1h)
- Vault 경로 입력 + 검증
- 폴더/파일명 패턴
- 자동 export 토글
- Frontmatter 커스터마이징

### M7: 통합 테스트 (1h)
- 정상 export 시나리오
- vault 미설정 시나리오
- 경로 탐색 공격 차단
- atomic write 실패 복구
- 자동 export (파이프라인 완료)

---

## 의존성

### 신규 Python 패키지
- `pyyaml` — YAML frontmatter 생성 (이미 설치되어 있을 가능성 높음, 확인 필요)

### 신규 Flutter 패키지
- 없음 (`url_launcher`는 이미 프로젝트에 있을 가능성)

---

## 리스크 완화

| 리스크 | 완화책 |
|---|---|
| vault 경로 변경 | 설정에서 경로 변경 시 기존 노트 경로 안내 |
| Obsidian Sync 충돌 | 단일 sync backend 권장 문서화 |
| 동시 export | Redis lock으로 동일 meeting_id 직렬화 |
| 파이프라인 영향 | ObsidianService 실패 시 독립 처리 (try/except + 로그) |
