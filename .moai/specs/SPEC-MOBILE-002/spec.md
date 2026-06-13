---
id: SPEC-MOBILE-002
version: "1.0.0"
status: draft
created: "2026-06-13"
updated: "2026-06-13"
author: Sisyphus
priority: medium
issue_number: 20
depends_on: SPEC-MOBILE-001
---

# SPEC-MOBILE-002: 오프라인 STT 처리 (On-Device Whisper)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 초기 작성 | Sisyphus |

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| Backend STT | mlx-whisper (server), whisper-base (on-device) |
| On-Device | whisper.cpp NNACE 추론 (cross-platform) |
| Client | Flutter + Riverpod |
| Connectivity | 기존 ConnectivityService 재사용 |
| 플랫폼 | iOS 15+, macOS 12+, Android 10+ |

## 2. 가정 (Assumptions)

- SPEC-MOBILE-001 모바일 인프라가 완성되어 있다
- 기기에 200MB 이상 여유 공간이 있다 (모델 150MB + 오디오)
- Wi-Fi 환경에서 최초 모델 다운로드를 수행한다
- 오프라인 STT 정확도는 서버(large-v3)보다 낮다 (whisper-base 기준)
- 네트워크 복구 시 서버 STT로 자동 재처리한다

## 3. 요구사항 (Requirements)

### REQ-MOBILE-002-001: 모델 관리 [P0]

**EARS 형식**: 앱이 최초 실행되었을 때, 시스템은 whisper-base 모델 다운로드를 제공하고 SHA-256으로 무결성을 검증해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-001-01 | whisper-base 모델 다운로드 URL 관리 | P0 | [NEW] |
| REQ-MOBILE-002-001-02 | SHA-256 체크섬 검증 | P0 | [NEW] |
| REQ-MOBILE-002-001-03 | 모델 버전 관리 (업데이트 감지) | P1 | [NEW] |
| REQ-MOBILE-002-001-04 | 로컬 모델 경로 관리 (앱 문서 디렉토리) | P0 | [NEW] |

---

### REQ-MOBILE-002-002: 오프라인 STT 엔진 [P0-CRITICAL]

**EARS 형식**: 네트워크가 연결되지 않았을 때, 시스템은 on-device whisper-base로 음성을 텍스트로 변환해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-002-01 | whisper.cpp 추론 엔진 통합 | P0 | [NEW] |
| REQ-MOBILE-002-002-02 | 오디오 전처리 (16kHz mono WAV 변환) | P0 | [NEW] |
| REQ-MOBILE-002-002-03 | 한국어 언어 설정 고정 | P0 | [NEW] |
| REQ-MOBILE-002-002-04 | 세그먼트별 타임스탬프 출력 | P0 | [NEW] |
| REQ-MOBILE-002-002-05 | 추론 진행률 콜백 | P1 | [NEW] |

---

### REQ-MOBILE-002-003: 하이브리드 파이프라인 [P0-CRITICAL]

**EARS 형식**: 네트워크 상태에 따라 시스템은 오프라인 우선 처리 후 온라인 재처리를 수행해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-003-01 | 오프라인 시 로컬 STT 우선 실행 | P0 | [NEW] |
| REQ-MOBILE-002-003-02 | 로컬 결과를 임시 표시 (low-confidence 마크) | P0 | [NEW] |
| REQ-MOBILE-002-003-03 | 네트워크 복구 시 서버 STT 자동 재처리 | P0 | [NEW] |
| REQ-MOBILE-002-003-04 | 재처리 완료 시 결과 교체 (无缝 전환) | P0 | [NEW] |
| REQ-MOBILE-002-003-05 | ConnectivityProvider 기반 자동 분기 | P0 | [NEW] |

---

### REQ-MOBILE-002-004: 모델 다운로드 UX [P1]

**EARS 형형**: 사용자가 모델을 다운로드할 때, 시스템은 Wi-Fi 여부 확인 및 진행률을 표시해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-004-01 | Wi-Fi 연결 시에만 다운로드 권장 | P1 | [NEW] |
| REQ-MOBILE-002-004-02 | 진행률 UI (progress bar) | P1 | [NEW] |
| REQ-MOBILE-002-004-03 | 다운로드 실패 시 재시도 버튼 | P1 | [NEW] |
| REQ-MOBILE-002-004-04 | 모델 크기 표시 (~150MB) | P2 | [NEW] |

---

### REQ-MOBILE-002-005: 백엔드 재처리 지원 [P1]

**EARS 형식**: 오프라인 처리 결과가 있는 오디오가 업로드되었을 때, 시스템은 서버 STT로 재처리하고 결과를 교체해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-005-01 | POST /transcriptions에 local_result 메타데이터 전달 | P1 | [NEW] |
| REQ-MOBILE-002-005-02 | transcription_source 필드 (local/server/hybrid) | P1 | [NEW] |
| REQ-MOBILE-002-005-03 | 기존 파이프라인 호환성 유지 | P0 | [NEW] |

---

## 4. MVP 범위에서 제외

| 기능 | 제외 사유 | 향후 SPEC |
|------|---------|-----------|
| whisper-large on-device | 모델 크기 과대 (3GB+) | — |
| 플랫폼별 네이티브 가속 (CoreML/TFLite) | 복잡도 과대, 우선 호환성 | SPEC-MOBILE-003 |
| 오프라인 Diarization | 모델 크기 + 정확도 한계 | — |
| 로컬 결과 편집 UI | 우선 서버 결과로 대체 | — |

## 5. 기술 설계

```
┌─────────────────────────────────────────────────┐
│  Flutter Client                                  │
│  ┌─────────────────────────────────────────────┐ │
│  │ PipelineProvider (하이브리드 분기)           │ │
│  │  ├─ online → 서버 업로드 (기존 플로우)       │ │
│  │  └─ offline → LocalSttService 추론           │ │
│  │       └─ 네트워크 복구 시 서버 재처리 큐     │ │
│  ├─────────────────────────────────────────────┤ │
│  │ ModelManager (다운로드/검증/버전)            │ │
│  │ LocalSttService (whisper.cpp 추론)           │ │
│  │ ReprocessQueue (온라인 복구 시 재처리)       │ │
│  └─────────────────────────────────────────────┘ │
└────────────────┬────────────────────────────────┘
                 │ (온라인 시)
┌────────────────▼────────────────────────────────┐
│  Backend FastAPI                                 │
│  POST /transcriptions                            │
│  └─ local_result 메타데이터 옵션 처리            │
│  └─ transcription_source 필드 추가               │
└─────────────────────────────────────────────────┘
```

### 신규 파일

```
client/
├── lib/services/
│   ├── local_stt_service.dart        [NEW] on-device whisper 추론
│   ├── model_manager.dart            [NEW] 모델 다운로드/검증
│   └── reprocess_queue.dart          [NEW] 온라인 복구 시 재처리
├── lib/providers/
│   ├── hybrid_pipeline_provider.dart [NEW] 오프라인/온라인 분기
│   └── model_download_provider.dart  [NEW] 다운로드 진행률 상태
├── lib/models/
│   └── transcription_source.dart     [NEW] local/server/hybrid enum
├── lib/screens/
│   └── model_download_screen.dart    [NEW] 다운로드 UX

backend/
├── schemas/
│   └── transcription.py              [MODIFY] local_result 옵션 추가
```

## 6. 의존성 (Dependencies)

| 선행 SPEC | 내용 |
|-----------|------|
| SPEC-MOBILE-001 | 모바일 인프라 (녹음, ConnectivityService) |

**Client 의존성**:
```yaml
# whisper.cpp Flutter 바인딩 — 패키지 선택 필요
# 옵션: whisper_flutter_new / whisper_ggml / platform FFI
```

## 7. 구현 현황

| 항목 | 상태 |
|------|------|
| on-device whisper | 미구현 |
| 하이브리드 파이프라인 | 미구현 |
| 모델 다운로드 UX | 미구현 |
| ConnectivityService | 기존 구현 존재 (재사용 가능) |
| 백엔드 재처리 | 미구현 |

## 8. 기술 제약사항

| 제약 | 설명 |
|------|------|
| 모델 크기 | whisper-base ~150MB (다운로드 필요) |
| 추론 속도 | 실시간의 1-3배 (기기 성능 의존) |
| 한국어 정확도 | whisper-base 기준 ~85% (large-v3 대비 낮음) |
| 메모리 | 추론 시 ~500MB 추가 사용 |
| 플랫폼 | iOS/macOS/Android 각각 네이티브 빌드 필요 |

---
*SPEC ID: SPEC-MOBILE-002*
*생성일: 2026-06-13*
*상태: draft*
