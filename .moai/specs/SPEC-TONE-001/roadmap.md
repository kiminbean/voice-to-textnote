# 발화 톤/감정 분석 통합 로드맵

> Date: 2026-06-14
> Status: Planning
> Related Research: `research.md`, `research-client.md`, `research-ser.md`

## 1. 배경: 리서치에서 발견된 상황

"발화 톤/감정 분석"을 단일 SPEC으로 기획하려 했으나, 깊은 리서치 결과 **감정 분석 텍스트 파이프라인이 이미 ~85% 구현**되어 있음이 발견되었습니다.

### 1.1 현재 구현 상태

| 컴포넌트 | 상태 | 위치 |
|----------|------|------|
| LLM 텍스트 감정 분석 (10 emotions) | ✅ 구현됨 | `backend/pipeline/sentiment_analyzer.py`, `sentiment_task.py` |
| Lexicon 기반 감성 분석 (POS/NEG/NEU) | ✅ 구현됨 | `backend/services/sentiment_service.py` |
| 감정 분석 API (8개 엔드포인트) | ✅ 구현됨 | `backend/app/api/v1/analytics/sentiment.py` |
| 감정 분석 스키마 | ✅ 구현됨 | `backend/schemas/sentiment.py` (87 lines) |
| Flutter 감정 카드 위젯 | ✅ 구현됨 | `client/lib/screens/result_screen.dart:714-855` |
| Flutter 감정 API 서비스 | ✅ 구현됨 | `client/lib/services/sentiment_api.dart` |
| **Celery 태스크 등록** | ✅ 구현됨 | `backend/workers/celery_app.py`에 tone/sentiment task 등록 |
| **SPEC 문서** | ❌ **없음** | `.moai/specs/SPEC-SENTIMENT-001/` 디렉토리 미존재 |
| **SSE 진행률 스트리밍** | ✅ 구현됨 | `task:tone:status:` prefix 포함 |
| **emotional_timeline 렌더링** | ✅ 구현됨 | tone timeline 위젯과 에러 격리 섹션 구현 |
| 오디오 기반 감정 인식 (SER) | ❌ 미구현 | (새 기능) |
| 발화 톤/운율 분석 (prosody) | ✅ 구현됨 | SPEC-TONE-001 M1~M6 완료 |
| 오디오 세그먼트 보존 | ✅ 구현됨 | tone_task 완료 후 DIA wav 정리로 이연 |

### 1.2 README 부정확성

README에 "Claude 3.5 Sonnet" 사용으로 명시되어 있으나, 실제 구현은 **OpenAI `gpt-4o-mini`** (`config.py:78-84`에서 `anthropic_api_key`는 "미사용" 표시). 이 README 오류는 SPEC-SENTIMENT-001 문서화 시 함께 수정 필요.

---

## 2. 3-SPEC 분할 전략

기능의 복잡도, 의존성, 구현 난이도를 고려해 **3개 독립 SPEC**으로 분할합니다.

### SPEC-SENTIMENT-001: 텍스트 감정 분석 통합 완료 (P1 - 최우선)

**유형**: Brownfield 문서화 + 버그 수정 + UI 완성

**목표**: 이미 구현된 텍스트 감정 분석 기능을 프로덕션에서 실제로 동작하게 만들고, 요구사항 추적성을 확보.

**범위**:
- Backend 버그 수정 (3곳)
  - `celery_app.py` include[]에 `sentiment_task` 추가 (1줄, CRITICAL)
  - `stream.py` SSE prefix 루프에 `task:sentiment:status:` 추가 (1줄)
  - (선택) `minutes_task.py` 완료 후 자동 트리거 추가
- Flutter UI 완성
  - `_SentimentTab` 신규 탭 추가 (전용 탭으로 승격)
  - `emotional_timeline` 시각화 (시계열 차트)
  - `SpeakerSentiment` precomputed 데이터 렌더링
  - silent failure → error retry UI로 개선
- 문서화
  - 역추적 SPEC 문서 작성 (이미 구현된 코드의 요구사항 정의)
  - README "Phase 5" 섹션 수정 ("완료"로 이동 + Claude→OpenAI 정정)
- 테스트
  - 감정 분석 통합 테스트 (실제 Celery 실행 확인)
  - Flutter 위젯 테스트

**예상 기간**: 1-2일

**수정 대상 파일** (예상):
| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `backend/workers/celery_app.py` | 수정 (1줄) | `include` 리스트에 sentiment_task 추가 |
| `backend/app/api/v1/transcription/stream.py` | 수정 (1줄) | SSE prefix 튜플에 sentiment 추가 |
| `backend/workers/tasks/minutes_task.py` | 수정 (선택) | MIN 완료 후 sentiment 자동 트리거 |
| `backend/app/config.py` | 수정 | `MAX_CONCURRENT_SENTIMENT` 설정 이관 |
| `client/lib/screens/result_screen.dart` | 수정 | `_SentimentTab` 신규 + 탭 추가 |
| `client/lib/services/sentiment_api.dart` | 수정 | timeline, speaker_sentiment getter 추가 |
| `client/lib/providers/result_provider.dart` | 수정 | precomputed 데이터 사용 |
| `README.md` | 수정 | Phase 5 → 완료 섹션 이동 + 모델 정정 |
| `.moai/specs/SPEC-SENTIMENT-001/spec.md` | 신규 | 역추적 SPEC 문서 |
| `.moai/specs/SPEC-SENTIMENT-001/plan.md` | 신규 | 구현 계획 |
| `.moai/specs/SPEC-SENTIMENT-001/acceptance.md` | 신규 | 검수 기준 |

**라이브러리 의존성**: 없음 (기존 OpenAI SDK, Pydantic, Riverpod만 사용)

**리스크**: 낮음. 이미 구현된 코드의 버그 수정 + 문서화이므로 기능적 리스크 최소.

---

### SPEC-TONE-001: 발화 톤/운율 분석 (P2)

**유형**: 신규 기능 + 아키텍처 변경

**목표**: 텍스트와 무관한 음향 특징(pitch, energy, speaking rate)을 추출해 발화 톤을 분류. SPEC-SENTIMENT-001의 텍스트 감정과 융합 가능한 독립 차원 제공.

**범위**:
- 아키텍처 변경 (오디오 보존)
  - `diarization_task.py`에서 DIA wav 삭제 시점 조정 (SER/TONE 태스크 완료 후로 이연)
  - 또는 세그먼트별 오디오 추출 후 `results_dir` 영구 저장
- Prosody 분석 엔진
  - `backend/ml/tone_engine.py` 신규 싱글톤 (WhisperEngine/DiarizationEngine 패턴 복제)
  - `opensmile` v2.6.0 (eGeMAPSv02, 88 features) + `librosa` (F0, energy, speaking rate)
  - tone 분류: calm/excited/authoritative/hesitant/monotone (meeting-specific 5-class)
- Celery 태스크
  - `backend/workers/tasks/tone_task.py` 신규
  - DIA 완료 후 트리거 (minutes와 병렬)
- 스키마 확장
  - `backend/schemas/tone.py` 신규 (ToneSegment, SpeakerTone, ToneResponse)
  - `DiarizedSegmentResult`에 `tone` 필드 optional 추가
- API 엔드포인트
  - `backend/app/api/v1/analytics/tone.py` 신규 (`/tone/meeting/{id}`, `/tone/{task_id}`)
- Flutter 통합
  - `client/lib/services/tone_api.dart` 신규
  - tone timeline 시각화 (pitch contour, energy envelope)
  - 감정 분석 탭 내 tone 섹션 추가 또는 별도 탭

**예상 기간**: 3-5일

**라이브러리 의존성**:
| 라이브러리 | 버전 | 용도 | License |
|-----------|------|------|---------|
| `opensmile` | ^2.6.0 | eGeMAPSv02 감정 특화 feature (88차원) | AGPL-3.0 ⚠️ |
| `librosa` | ^0.10.0 | F0/pyin, RMS energy, mel-spec | ISC ✅ |
| `numpy` | (기존) | 수치 연산 | BSD ✅ |

**⚠️ opensmile AGPL-3.0 라이선스 리스크**: opensmile은 AGPL-3.0으로, 네트워크 서비스로 제공 시 소스 공개 의무 발생 가능. 대안 검토 필요:
- (a) 사내/로컬 전용 사용으로 AGPL 의회 회피 (현재 voice-to-textnote는 로컬 전용이므로 가능)
- (b) `pyannote-audio`의 내부 feature extractor 사용 (MIT)
- (c) `torchaudio` 기반 직접 구현 (BSD)

**의존성**: SPEC-SENTIMENT-001 완료 후 착수 권장 (감정+톤 융합을 위해)

**리스크**:
- 오디오 보존 정책 변경이 디스크 사용량에 미치는 영향 (1시간 회의 × N세그먼트 × 16kHz 모노)
- AGPL 라이선스 검증 필요
- tone 분류 체계(5-class)의 한국어 회의 데이터 검증 부족 → 자체 eval set 구축 필수

---

### SPEC-SER-001: 오디오 기반 감정 인식 (P3)

**유형**: 신규 기능 + 외부 모델 도입 + 하이브리드 fusion

**목표**: 음성 신호 자체에서 감정을 인식(SER)하여 텍스트 기반 감정과 융합. 비언어적 감정 단서(한숨, 억양 강조, 떨림)를 포착.

**범위**:
- SER 엔진
  - `backend/ml/ser_engine.py` 신규 싱글톤
  - `emotion2vec_plus_base` (~90M, ~360MB fp32) via FunASR — cross-lingual (한국어 포함 10개 언어)
  - 9-class 출력: angry/disgusted/fearful/happy/neutral/other/sad/surprised/unknown
- 하이브리드 fusion
  - `backend/pipeline/emotion_fusion.py` 신규
  - Adaptive Late Fusion (학습 가중치) + Claude/OpenAI fallback (low confidence 케이스)
  - 9-class SER + 10-class 텍스트 감정 → meeting 7-class 통합 매핑
- Celery 태스크
  - `backend/workers/tasks/ser_task.py` 신규
  - DIA 완료 후 tone_task와 병렬 실행
- 스키마 확장
  - `backend/schemas/emotion.py` 신규 (FusedEmotion, AudioEmotion, EmotionFusionResult)
  - `SentimentSegment`에 `audio_emotion`, `fused_emotion` 필드 optional 추가
- API 엔드포인트
  - `backend/app/api/v1/analytics/emotion.py` 신규 (`/emotion/meeting/{id}`, `/emotion/{task_id}/fusion`)
- Flutter 통합
  - 오디오 감정 vs 텍스트 감정 비교 시각화
  - fusion confidence 표시
  - disagreement 케이스 하이라이트

**예상 기간**: 1-2주 (모델 검증 + fusion 튜닝 포함)

**라이브러리 의존성**:
| 라이브러리 | 버전 | 용도 | License |
|-----------|------|------|---------|
| `funasr` | ^1.2.7 | emotion2vec+ 모델 로드/추론 (MPS 지원) | MIT ✅ |
| `transformers` | (기존 추정) | 모델 로딩 인프라 | Apache-2.0 ✅ |
| `torch` | (기존 추정) | 추론 | BSD ✅ |

**⛔ Critical Blocker: emotion2vec+ License**

`emotion2vec_plus_base/large`의 라이선스는 "model-license" (비-Apache)로, 상용 사용 제한이 불명확합니다. SPEC-SER-001 착수 전 반드시:
1. Alibaba DAMO Academy에 상용 사용 가능 여부 문의
2. 불가능 시 fallback: `jungjongho/wav2vec2-xlsr-korean-speech-emotion-recognition` (Apache-2.0, 단 정확도 하락 76.67%)

**의존성**: SPEC-TONE-001 완료 후 착수 (오디오 보존 아키텍처가 선행되어야 함)

**리스크**:
- 한국어 SER 현실적 정확도 55-65% UAR (ASR의 95%+와 큰 차이) → 사용자 기대치 관리 필요
- MPS 미지원 op 런타임 에러 → `PYTORCH_ENABLE_MPS_FALLBACK=1` 필수
- 메모리 예산: 현재 ~12GB 사용 중, 경고선 19.2GB → SER 모델 ~360MB 추가는 안전
- License 검증 실패 시 전체 SPEC 재설계 필요

---

## 3. 의존성 그래프

```
[현재: 감정 분석 코드 존재하나 동작 안 함]
                    │
                    ▼
         ┌─────────────────────┐
         │ SPEC-SENTIMENT-001  │ ← P1, 1-2일
         │ 텍스트 감정 분석     │   (버그 수정 + 문서화 + UI)
         │ 통합 완료            │
         └──────────┬──────────┘
                    │ (완료 후)
                    ▼
         ┌─────────────────────┐
         │ SPEC-TONE-001       │ ← P2, 3-5일
         │ 발화 톤/운율 분석    │   (오디오 보존 아키텍처 선행)
         │ (prosody)           │
         └──────────┬──────────┘
                    │ (완료 후)
                    ▼
         ┌─────────────────────┐
         │ SPEC-SER-001        │ ← P3, 1-2주
         │ 오디오 기반 감정     │   (license 검증 선행 필수)
         │ 인식 (SER)          │
         │ + 하이브리드 fusion │
         └─────────────────────┘
```

### 3.1 의존성 근거

- **SENTIMENT-001 → TONE-001**: tone 분석 결과를 텍스트 감정과 융합하려면, 먼저 감정 분석이 실제로 동작해야 함 (현재는 Celery 미등록으로 동작 안 함)
- **TONE-001 → SER-001**: 둘 다 오디오 보존 아키텍처가 필요. TONE-001에서 이 아키텍처를 설계/구현하면 SER-001은 재사용 가능. 역순으로 하면 아키텍처가 중복 설계됨.

---

## 4. 우선순위 권장사항

### 4.1 1순위: SPEC-SENTIMENT-001

**권장 이유**:
1. **가장 빠른 가치 실현** (1-2일): 이미 85% 구현된 기능을 즉시 프로덕션 가동
2. **가장 낮은 리스크**: 버그 수정 + 문서화이므로 새 기능 리스크 없음
3. **기반 역할**: 이후 SPEC들의 전제 조건 (감정 분석이 동작해야 tone/SER와 비교/융합 가능)
4. **사용자 가치 즉시 확보**: 현재 감정 분석 기능이 UI에 보이지만 동작하지 않는 좌절 해소

### 4.2 병렬 진행 가능 작업

SPEC-SENTIMENT-001 실행 중 병렬로 진행할 수 있는 작업:
- **emotion2vec+ license 검증** (Alibaba DAMO 문의) — SPEC-SER-001의 critical blocker이므로 조기 착수 권장
- **tone 분류 체계 설계** — 회의 데이터 기반 5-class 분류 기준 수립 (데이터 과학자 작업)

---

## 5. 총 예상 기간 및 리소스

| SPEC | 예상 기간 | 난이도 | 외부 의존성 |
|------|-----------|--------|-------------|
| SPEC-SENTIMENT-001 | 1-2일 | 낮음 | 없음 |
| SPEC-TONE-001 | 3-5일 | 중간 | opensmile AGPL 검증 |
| SPEC-SER-001 | 1-2주 | 높음 | emotion2vec+ license, 한국어 SER 정확도 |
| **총합** | **2-3주** | - | - |

### 5.1 메모리 예산 (M4 Mac mini 24GB)

| 컴포넌트 | 메모리 | 단계 |
|----------|--------|------|
| 현재 사용 (Whisper+pyannote+FastAPI+Redis) | ~12GB | 기준 |
| SPEC-SENTIMENT-001 (OpenAI API, 추가 모델 없음) | +0GB | 1-2일 |
| SPEC-TONE-001 (opensmile + librosa) | +0.1GB | 3-5일 |
| SPEC-SER-001 (emotion2vec_plus_base fp32) | +0.4GB | 1-2주 |
| **최종 총합** | **~12.5GB** | 경고선 19.2GB 내 안전 |

---

## 6. 다음 단계

1. **이 로드맵 검토** (현재 단계)
2. **첫 번째 SPEC 선택** — SENTIMENT-001 권장
3. **`/moai plan` 재실행** 또는 plan 워크플로우 계속 진행으로 선택한 SPEC의 상세 문서 작성
4. (병렬) emotion2vec+ license 검증 착수

---

## 7. 원본 리서치 산출물 참조

상세 기술 정보는 다음 파일 참조:
- `research.md`: STT 파이프라인, 세그먼트 데이터 모델, 오디오 생명주기, ML 로딩 패턴
- `research-client.md`: API/스키마/Flutter 통합 패턴, 기존 감정 분석 코드 상세
- `research-ser.md`: SER 모델 비교, 한국어 텍스트 감정 모델, fusion 전략, memory 예산
