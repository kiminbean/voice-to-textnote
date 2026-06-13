# Implementation Plan: SPEC-MOBILE-002

## 오프라인 STT 처리 (On-Device Whisper)

## 개요

오프라인 환경에서 on-device whisper-base 모델로 STT 처리. 하이브리드 파이프라인(오프라인 우선 → 온라인 재처리) 구현.

## 요구사항 모듈 (5개)

### REQ-MOBILE-002-001: 모델 관리 [P0]

**EARS**: 앱 최초 실행 시 whisper-base 다운로드 제공 및 SHA-256 검증.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 001-01 | 모델 다운로드 URL 관리 | P0 |
| 001-02 | SHA-256 검증 | P0 |
| 001-04 | 로컬 경로 관리 | P0 |

### REQ-MOBILE-002-002: 오프라인 STT 엔진 [P0-CRITICAL]

**EARS**: 오프라인 시 on-device whisper-base로 STT 실행.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 002-01 | whisper.cpp 추론 통합 | P0 |
| 002-02 | 오디오 전처리 (16kHz WAV) | P0 |
| 002-03 | 한국어 고정 | P0 |
| 002-04 | 세그먼트 타임스탬프 | P0 |

### REQ-MOBILE-002-003: 하이브리드 파이프라인 [P0-CRITICAL]

**EARS**: 네트워크 상태에 따라 오프라인 우선, 온라인 재처리.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 003-01 | 오프라인 시 로컬 STT 우선 | P0 |
| 003-02 | 로컬 결과 임시 표시 | P0 |
| 003-03 | 네트워크 복구 시 자동 재처리 | P0 |
| 003-05 | ConnectivityProvider 기반 분기 | P0 |

### REQ-MOBILE-002-004: 모델 다운로드 UX [P1]

**EARS**: Wi-Fi 확인 + 진행률 UI + 재시도.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 004-01 | Wi-Fi 권장 | P1 |
| 004-02 | 진행률 progress bar | P1 |
| 004-03 | 재시도 버튼 | P1 |

### REQ-MOBILE-002-005: 백엔드 재처리 [P1]

**EARS**: local_result 메타데이터 전달 및 transcription_source 필드.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 005-01 | local_result 메타데이터 옵션 | P1 |
| 005-02 | transcription_source 필드 | P1 |
| 005-03 | 기존 파이프라인 호환성 | P0 |

## 기술 스택

**Client**: Flutter, whisper.cpp NNACE, Riverpod, Dio
**Backend**: FastAPI (기존 transcription API 확장)

## 작업 분해 (Task Decomposition)

### Phase 1: 모델 관리 + 다운로드 (P0-P1)

- T-001: `model_manager.dart` — 다운로드, SHA-256 검증, 버전 관리
- T-002: `model_download_provider.dart` — 진행률 상태 관리
- T-003: `model_download_screen.dart` — Wi-Fi 체크, progress UI, 재시도

### Phase 2: 오프라인 STT 엔진 (P0)

- T-004: `local_stt_service.dart` — whisper.cpp 추론 래퍼 + 전처리
- T-005: `transcription_source.dart` — local/server/hybrid enum
- T-006: LocalSttService 단위 테스트 (mock 추론)

### Phase 3: 하이브리드 파이프라인 (P0)

- T-007: `reprocess_queue.dart` — 온라인 복구 시 재처리 큐
- T-008: `hybrid_pipeline_provider.dart` — ConnectivityProvider 기반 분기
- T-009: PipelineProvider 수정 — offline 경로 통합
- T-010: 하이브리드 파이프라인 단위 테스트

### Phase 4: 백엔드 재처리 지원 (P1)

- T-011: `schemas/transcription.py` — local_result 옵션, source 필드
- T-012: 백엔드 transcription API 수정 — local_result 처리
- T-013: 백엔드 단위 테스트

### Phase 5: 통합 및 마무리 (P1)

- T-014: 회의록 화면에 로컬 결과 임시 표시 UI
- T-015: 재처리 완료 시 결과 교체 UX
- T-016: 전체 테스트 실행 및 회귀 검증

## 위험 분석

| 위험 | 확률 | 영향 | 완화 |
|------|------|------|------|
| whisper.cpp 패키지 호환성 | 중간 | 높음 | 추상화 레이어로 플랫폼 분리 |
| 모델 다운로드 실패 | 중간 | 중간 | 재시도 + 캐시 |
| 추론 속도로 UX 저하 | 높음 | 중간 | 진행률 표시 + 백그라운드 처리 |
| 메모리 부족 | 낮음 | 높음 | 기기 메모리 체크 |

## 검증 전략

1. **단위 테스트**: ModelManager, LocalSttService, ReprocessQueue
2. **회귀 테스트**: 기존 백엔드 + Flutter 전체 통과
3. **수동 테스트**: 비행기 모드 → 녹음 → 로컬 STT → 네트워크 복구 → 재처리

---
*작성일: 2026-06-13*
*작성자: Sisyphus*
*상태: draft*
