# CG 작업계획서: 테스트 커버리지 보강

> 작성 2026-06-02 (Opus lead 세션) · 실행 대상: `moai cg` 새 세션의 GLM teammate
> 이 문서는 자기완결적이다. 대화 컨텍스트 없이 이 문서만으로 작업 가능하도록 작성됨.

## 0. 배경 (왜 이 작업인가)

- origin/main 13커밋(OAuth, Q&A, vocabulary, Phase 2-4)과 로컬 기능(고급 통계·화자 관리)을 rebase 머지함.
- 환경 결함 수리: venv가 Python 3.14라 표준 `audioop`이 PEP 594로 제거됨 → `pydub` import 실패로 테스트 166 error. **`audioop-lts` 설치로 해결 완료**.
- 그 결과 전역 커버리지 **74% → 89%** (게이트 85% 통과). 따라서 본 작업은 전역 게이트가 아니라 **저커버리지 신규 기능 모듈의 회귀 방지 테스트 보강**이 목표.

## 1. 환경 (필수 — 반드시 준수)

```bash
# repo 루트에서 실행. 인터프리터는 프로젝트 venv 고정 (anaconda 금지)
cd /Users/ibkim/Projects/voice-to-textnote
# import 컨벤션: repo 루트가 PYTHONPATH, 모든 import는 `from backend.X import ...`
# audioop-lts 설치 확인 (미설치 시: venv/bin/pip install audioop-lts)
PYTHONPATH=. venv/bin/python -c "import audioop; print('ok')"
```

- 테스트 실행: `PYTHONPATH=. venv/bin/python -m pytest backend/tests/<file> -q -p no:cacheprovider`
- pytest 설정(pyproject.toml): `testpaths=["backend"]`, `--cov-fail-under=85`. 부분 실행 시 전체 커버리지 게이트가 FAIL로 찍혀도 개별 테스트 pass면 정상.
- 코드 주석/문서는 한국어, 식별자는 영어.

## 2. 테스트 패턴 참조 (기존 통과 테스트를 템플릿으로)

- API 엔드포인트 테스트: `backend/tests/unit/test_vocabulary_api.py`, `backend/tests/unit/test_team_api.py`
- 품질 모니터링(로컬 신규기능) 테스트: `backend/tests/unit/test_quality_monitoring_api.py`
- 공통 fixture: `backend/conftest.py` (앱/DB 세션/클라이언트 fixture 확인 후 재사용)
- 신규 테스트는 위 파일들의 fixture·스타일을 그대로 따를 것. 새 fixture 도입 시 사유 명시.

## 3. 작업 목록 (우선순위)

### P1 — 최근 머지 기능 (회귀 방지 최우선)

| 모듈 | 현재 cov | 테스트 대상 (공개 표면) |
|------|---------:|------------------------|
| `app/api/v1/enhanced_statistics.py` | 0% | `GET /{task_id}` (get_enhanced_statistics), `GET /overview` (get_project_overview) |
| `app/api/v1/quality_assessment.py` | 43% | 신규 엔드포인트: `GET .../quality-score` (get_live_quality_score), `POST .../quality-feedback` (submit_quality_feedback), `GET .../quality-feedback` (list_quality_feedback), `GET .../quality-trends` |
| `services/quality_service.py` | 44% | 신규 메서드: `compute_live_score`, `submit_feedback`, `get_feedback_summary`, `get_quality_trends` (line 833~) |
| `services/speaker_voice_service.py` | low | `analyze_upload`, `create_or_replace_from_samples`, `get_characteristics`, `to_characteristics_response` |

각 항목별 테스트 요건:
- 정상 경로 + 경계/오류 경로(존재하지 않는 task_id → 404, 잘못된 입력 → 422, 빈 결과) 모두 커버.
- ZAI 호출이 있는 경로(`assess_minutes`, `compute_live_score` 일부)는 `get_zai_client`를 mock하여 AI 호출 없이 검증. `ZAI_API_KEY` 미설정 환경에서도 통과해야 함.
- DB 의존은 기존 conftest의 테스트 세션 fixture 사용.

### P2 — origin 신규 미테스트

| 모듈 | 현재 cov | 테스트 대상 |
|------|---------:|------------|
| `services/qa_service.py` | 21% | `ask`, `get_history` (Q&A, ZAI mock 필요) |
| `services/oauth_service.py` | 25% | `verify_google_token`, `verify_apple_token`, `verify_apple_code_callback` (외부 토큰 검증 — httpx/jwt mock) |
| `app/api/v1/batch.py` | 21% | `POST` upload_batch_transcription, `GET` get_batch_status |
| `app/api/v1/audio_preprocess.py` | 23% | 라우트 점검 후 정상/오류 경로 |

## 4. 작업 방식 (GLM teammate)

- 모듈 1개 = 작업 단위. 한 번에 한 테스트 파일을 작성·실행·통과시킨 뒤 다음으로.
- 파일 소유: 신규 테스트 파일만 생성/수정. 소스 코드는 수정 금지(테스트가 버그를 드러내면 보고만).
- 각 모듈 완료 시 해당 테스트 파일 실행해 통과 + 대상 모듈 커버리지 상승 확인.

## 5. 완료 기준 (검증)

```bash
# 신규/대상 테스트만 빠르게
PYTHONPATH=. venv/bin/python -m pytest backend/tests/unit/test_enhanced_statistics.py \
  backend/tests/unit/test_quality_monitoring_api.py -q -p no:cacheprovider
# 전체 + 커버리지 (최종)
PYTHONPATH=. venv/bin/python -m pytest backend --cov=backend --cov-report=term-missing -q -p no:cacheprovider
```

- 완료 목표: P1 모듈 각 70%+ 커버리지, 전역 커버리지 89% → 92%+ 유지, 신규 테스트 전부 pass.
- 별도 트랙(이 계획서 범위 외): audioop 수리 후에도 남은 16개 failures 디버깅 → Opus 세션 권장.

## 6. moai cg 진입

```bash
moai cg        # Lead=Claude + Teammates=GLM. 이미 tmux 안 + GLM 키 등록 완료
# 새 세션에서: 이 문서(.moai/work-plans/test-coverage-cg.md)를 읽고 P1부터 실행하도록 지시
```
