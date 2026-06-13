---
id: SPEC-MOBILE-002
version: "1.0.0"
status: implementation-complete
created: "2026-06-10"
updated: "2026-06-11"
author: kisoo
priority: medium
issue_number: 20
---

# SPEC-MOBILE-002: 오프라인 STT 처리 (On-Device Whisper)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-10 | 초안 작성 — 오프라인 STT 처리 아키텍처 설계 | kisoo |
| 1.0.1 | 2026-06-11 | 코드 기준 구현 완료 상태 반영 — T-001~T-024 완료, 실제 파일명 정정 | Codex |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 프레임워크 | Flutter 3.24+ / Dart 3.5+ |
| 상태관리 | Riverpod 2.6+ (flutter_riverpod) |
| 온디바이스 STT 엔진 | whisper.cpp (C++ core, 플랫폼 바인딩) |
| 모델 | whisper-base (~150MB, 한국어 최적화) |
| 플랫폼 바인딩 | iOS: Core ML / macOS: mlx-whisper / Android: TFLite |
| 네트워크 감지 | connectivity_plus (기존 ConnectivityService 활용) |
| 오디오 전처리 | ffmpeg-kit 또는 flutter_ffmpeg (16kHz mono WAV 변환) |
| 로컬 저장소 | path_provider (모델 캐시), sqflite (태스크 큐) |
| 대상 플랫폼 | iOS 15+, Android 10+ (API 29+), macOS 13+ |
| 백엔드 STT | whisper-large-v3 (온라인 재처리용, 기존 파이프라인) |
| 선행 SPEC | SPEC-MOBILE-001 (completed), SPEC-APP-001 (completed) |

---

## 2. 가정 (Assumptions)

- Flutter 클라이언트는 기존에 오디오 녹음(M4A) 및 백엔드 업로드 파이프라인을 갖추고 있다 (`client/lib/services/audio_api.dart`, `client/lib/providers/pipeline_provider.dart`).
- 백엔드는 이미 whisper-large-v3 기반 STT 파이프라인을 운영 중이다 (`backend/ml/stt_engine.py`).
- connectivity_plus 기반 ConnectivityService와 OfflineBanner 위젯이 이미 존재한다.
- whisper-base 모델(~150MB)은 whisper.cpp를 통해 iOS/Android/macOS 모두에서 실시간 처리가 가능하다 (Snapdragon 8 Gen 2, Apple A15 이상).
- 모델 다운로드는 최초 실행 시에만 필요하며, Wi-Fi 환경에서 진행된다.
- 한국어가 기본 언어이며, 다국어 지원은 향후 SPEC으로 분리한다.
- 오프라인 STT 결과는 온라인 복구 시 whisper-large-v3로 재처리하여 정확도를 높인다.
- macOS 클라이언트는 기존 백엔드 mlx-whisper와 동일 엔진을 활용할 수 있다.

---

## 3. 요구사항 (Requirements)

### REQ-MOBILE-007: 온디바이스 Whisper 모델 관리 (Model Management)

**EARS 형식**: **WHEN** 앱이 최초로 실행되거나 모델 버전이 변경될 때, 시스템은 whisper-base 모델을 안전하게 다운로드하고 로컬에 저장하여 오프라인 STT 처리에 사용할 수 있도록 준비**해야 한다 (shall)**.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-007-01 | whisper-base 모델 파일(~150MB)을 앱 내부 저장소에 다운로드하고 저장한다 | P1 | [NEW] |
| REQ-MOBILE-007-02 | 모델 파일의 SHA-256 체크섬을 검증하여 무결성을 보장한다 | P1 | [NEW] |
| REQ-MOBILE-007-03 | 모델 버전 정보를 로컬에 저장하고, 서버에서 새 버전 확인 시 업데이트를 트리거한다 | P2 | [NEW] |
| REQ-MOBILE-007-04 | 기기 저장 공간이 부족할 경우(모델 크기의 2배 이상 여유 필요) 다운로드를 차단하고 사용자에게 안내한다 | P1 | [NEW] |
| REQ-MOBILE-007-05 | 모델 다운로드 중 앱이 종료되면 부분 다운로드 파일을 정리하고, 재시작 시 이어서 다운로드한다(resumable download) | P2 | [NEW] |
| REQ-MOBILE-007-06 | 모델 파일은 앱 삭제 시 함께 제거되도록 앱 내부 저장소(app documents directory)에 보관한다 | P1 | [NEW] |

---

### REQ-MOBILE-008: 오프라인 STT 처리 엔진 (Offline STT Engine)

**EARS 형식**: **WHEN** 네트워크 연결이 불가능하고 사용자가 녹음을 완료했을 때, 시스템은 온디바이스 whisper.cpp 엔진으로 로컬 STT 처리를 수행하여 결과를 제공**해야 한다 (shall)**.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-008-01 | 녹음된 M4A 오디오를 16kHz mono WAV로 변환하는 전처리 파이프라인을 구현한다 | P1 | [NEW] |
| REQ-MOBILE-008-02 | whisper.cpp Flutter 플랫폼 채널을 통해 온디바이스 STT 추론을 실행한다 | P1 | [NEW] |
| REQ-MOBILE-008-03 | STT 처리 진행률을 실시간으로 UI에 표시한다 (0% ~ 100%) | P2 | [NEW] |
| REQ-MOBILE-008-04 | STT 처리 중 메모리 사용량을 모니터링하고, 기기 메모리 부족 시 처리를 중단하고 사용자에게 안내한다 | P1 | [NEW] |
| REQ-MOBILE-008-05 | 5분 초과 녹음물은 청크 단위(30초)로 분할하여 순차 처리하여 메모리 과부하를 방지한다 | P1 | [NEW] |
| REQ-MOBILE-008-06 | STT 처리 완료 후 임시 WAV 파일을 즉시 삭제하여 저장 공간을 확보한다 | P2 | [NEW] |
| REQ-MOBILE-008-07 | 오프라인 STT 결과에 `offline: true` 메타데이터를 부여하여 온라인 재처리 대상임을 표시한다 | P1 | [NEW] |

---

### REQ-MOBILE-009: 하이브리드 온/오프라인 파이프라인 (Hybrid Pipeline)

**EARS 형식**: **WHEN** 네트워크 상태가 오프라인에서 온라인으로 전환될 때, 시스템은 오프라인 처리된 결과를 백엔드 whisper-large-v3로 재처리하여 더 높은 정확도의 결과로 교체**해야 한다 (shall)**.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-009-01 | ConnectivityService의 네트워크 상태 변경 이벤트를 구독하여 온/오프라인 전환을 감지한다 | P1 | [NEW] |
| REQ-MOBILE-009-02 | 오프라인 상태에서 녹음 완료 시 로컬 STT 파이프라인을 자동으로 실행한다 | P1 | [NEW] |
| REQ-MOBILE-009-03 | 온라인 상태에서 녹음 완료 시 기존 백엔드 파이프라인을 우선 실행한다 | P1 | [NEW] |
| REQ-MOBILE-009-04 | 네트워크 복구 시 `offline: true` 메타데이터가 있는 결과를 자동으로 백엔드에 재전송하여 재처리한다 | P1 | [NEW] |
| REQ-MOBILE-009-05 | 재처리 완료 시 오프라인 결과를 온라인 결과로 교체하고, UI에 "개선된 결과" 배지를 표시한다 | P2 | [NEW] |
| REQ-MOBILE-009-06 | 재처리 중 오류 발생 시 기존 오프라인 결과를 유지하고, 사용자에게 수동 재시도 옵션을 제공한다 | P1 | [NEW] |
| REQ-MOBILE-009-07 | 오프라인/온라인 파이프라인 선택 로직을 PipelineProvider에 통합하여 기존 SSE+폴링 아키텍처와 일관성을 유지한다 | P1 | [NEW] |

---

### REQ-MOBILE-010: 모델 다운로드 UX (Model Download UX)

**EARS 형식**: **WHEN** 모델 다운로드가 필요할 때, 시스템은 Wi-Fi 연결 상태를 확인하고 진행률 UI를 제공하여 사용자가 다운로드 과정을 파악할 수 있도록 **해야 한다 (shall)**.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-010-01 | 모델 미다운로드 상태에서 STT 기능 접근 시 다운로드 안내 다이얼로그를 표시한다 | P1 | [NEW] |
| REQ-MOBILE-010-02 | Wi-Fi 연결 시에만 자동 다운로드를 시작하고, 셀룰러 연결 시에는 사용자 확인 후 진행한다 | P1 | [NEW] |
| REQ-MOBILE-010-03 | 다운로드 진행률을 퍼센트(0%~100%)와 예상 남은 시간으로 표시한다 | P2 | [NEW] |
| REQ-MOBILE-010-04 | 다운로드 중 네트워크 끊김 시 일시 정지하고, 복구 시 자동 재개한다 | P1 | [NEW] |
| REQ-MOBILE-010-05 | 다운로드 실패 시 최대 3회 자동 재시도하고, 실패 시 수동 재시도 버튼을 제공한다 | P2 | [NEW] |
| REQ-MOBILE-010-06 | 백그라운드 다운로드를 지원하여 앱 사용 중 끊김 없이 다운로드가 진행된다 | P2 | [NEW] |

---

### REQ-MOBILE-011: 플랫폼별 STT 통합 (Platform-Specific Integration)

**EARS 형식**: **WHEN** 각 플랫폼(iOS, macOS, Android)에서 STT 처리를 실행할 때, 시스템은 플랫폼에 최적화된 추론 엔진을 사용하여 최고의 성능을 제공**해야 한다 (shall)**.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-011-01 | iOS에서 whisper.cpp를 Core ML 백엔드와 연동하여 Neural Engine 가속을 활용한다 | P1 | [NEW] |
| REQ-MOBILE-011-02 | macOS에서 mlx-whisper를 직접 호출하여 기존 백엔드와 동일한 Apple Silicon 최적화를 활용한다 | P1 | [NEW] |
| REQ-MOBILE-011-03 | Android에서 whisper.cpp를 TFLite 런타임으로 실행하여 ARM NEON 최적화를 활용한다 | P1 | [NEW] |
| REQ-MOBILE-011-04 | 플랫폼 감지 로직을 통해 iOS/macOS/Android를 자동 식별하고 적절한 엔진을 로드한다 | P1 | [NEW] |
| REQ-MOBILE-011-05 | Flutter Platform Channel(MethodChannel)을 통해 Dart 코드와 네이티브 whisper.cpp/ML 코드 간 통신한다 | P1 | [NEW] |
| REQ-MOBILE-011-06 | 각 플랫폼별 성능 벤치마크(처리 시간, 메모리 사용량)를 로깅하여 모니터링한다 | P2 | [NEW] |

---

## 4. 제외 항목 (Exclusions)

| 기능 | 제외 사유 | 향후 SPEC |
|------|----------|----------|
| 실시간 스트리밍 STT (녹음 중 실시간 변환) | whisper.cpp는 배치 처리에 최적화되어 있으며, 실시간 처리는 추가 아키텍처 설계 필요. 1차 목표는 녹음 완료 후 처리 | SPEC-MOBILE-003 |
| 다국어 STT (한국어 외 언어 지원) | 한국어 우선 검증 후 다국어 확장. whisper-base는 다국어 지원이 가능하나 UI/UX 다국어와 함께 설계 필요 | SPEC-I18N-001 |
| 온디바이스 화자 분리(Diarization) | pyannote.audio 모델은 모바일 추론에 부적합(모델 크기 1GB+, GPU 필요). 화자 분리는 서버 전용 유지 | N/A |
| 오프라인 AI 요약 (Claude API 대체) | 로컬 LLM 추론은 현재 모바일 기기에서 비실용적. AI 요약은 온라인 전용 유지 | N/A |
| 모델 자동 압축/양자화 (INT4, INT8) | whisper.cpp가 이미 양자화된 모델을 지원하나, 본 SPEC에서는 공식 배포 모델 사용. 커스텀 양자화는 성능 검증 후 | SPEC-MOBILE-004 |

---

## 5. 기술 설계

### 5.1 아키텍처 개요

```
현재 (SPEC-MOBILE-001):
  Flutter App → HTTP Upload → FastAPI → Celery → STT → Push 알림
                                                        (whisper-large-v3)

변경 후:
  Flutter App → [연결 상태 확인]
                ├── 온라인: HTTP Upload → FastAPI → Celery → STT (기존)
                └── 오프라인: 로컬 오디오 전처리 → whisper.cpp → 결과 표시
                                                        ↓
                                              (네트워크 복구 시)
                                              백엔드 재처리 요청
                                              → whisper-large-v3 결과로 교체
```

### 5.2 하이브리드 파이프라인 상태 전이

```
[녹음 완료]
    ↓
[네트워크 상태 확인] ── 온라인 ──→ [기존 백엔드 파이프라인] → 완료
    │
    └── 오프라인 ──→ [모델 다운로드 여부 확인]
                        ├── 미다운로드 → [다운로드 안내 UI]
                        └── 다운로드 완료 → [로컬 STT 파이프라인]
                                              ↓
                                        [오프라인 결과 표시]
                                        (offline: true 메타데이터)
                                              ↓
                              [네트워크 복구 감지]
                                  ↓
                              [백엔드 재처리 요청]
                                  ↓
                              [온라인 결과로 교체]
                                  ↓
                              [완료 — "개선됨" 배지]
```

### 5.3 플랫폼별 엔진 매핑

```
Platform Channel (MethodChannel: "com.voicetextnote/stt")
    │
    ├── iOS ──→ whisper.cpp + Core ML Delegate
    │           (ANE 가속, whisper-base Core ML 포맷)
    │
    ├── macOS ──→ mlx-whisper 직접 호출
    │             (MPS 가속, 기존 백엔드와 동일 엔진)
    │
    └── Android ──→ whisper.cpp + TFLite Runtime
                    (ARM NEON 최적화, TFLite 양자화 모델)
```

### 5.4 디렉토리 구조 변경

```
client/
├── lib/
│   ├── services/
│   │   ├── offline_stt_service.dart        # [NEW] 오프라인 STT 오케스트레이터
│   │   ├── model_download_service.dart     # [NEW] 모델 다운로드/검증/버전 관리
│   │   ├── audio_preprocessor.dart         # [NEW] M4A → 16kHz WAV 변환
│   │   ├── hybrid_pipeline_service.dart    # [NEW] 온/오프라인 파이프라인 선택
│   │   └── platform_stt_service.dart       # [NEW] Platform Channel 바인딩
│   ├── providers/
│   │   ├── offline_stt_provider.dart       # [NEW] 오프라인 STT 상태 (Riverpod)
│   │   ├── model_download_provider.dart    # [NEW] 다운로드 진행률 상태
│   │   └── pipeline_provider.dart          # [MODIFY] 하이브리드 파이프라인 통합
│   ├── models/
│   │   ├── transcription_result.dart       # [MODIFY] offline 필드 추가
│   │   └── model_info.dart                 # [NEW] 모델 버전/상태 정보
│   ├── widgets/
│   │   ├── model_download_dialog.dart      # [NEW] 다운로드 진행 UI
│   │   ├── offline_result_badge.dart       # [NEW] "오프라인 처리됨" 배지
│   │   └── improved_result_badge.dart      # [NEW] "개선된 결과" 배지
│   └── screens/
│       └── recording_screen.dart           # [MODIFY] 오프라인 STT 트리거
├── ios/
│   └── Classes/
│       └── WhisperSttPlugin.swift          # [NEW] whisper.cpp + Core ML 바인딩
├── macos/
│   └── Classes/
│       └── MlxWhisperPlugin.swift          # [NEW] mlx-whisper 직접 호출
├── android/
│   └── app/src/main/kotlin/
│       └── com/voicetextnote/app/
│           └── WhisperSttPlugin.kt         # [NEW] whisper.cpp + TFLite 바인딩
└── pubspec.yaml                            # [MODIFY] 의존성 추가
```

### 5.5 의존성 추가

```yaml
# pubspec.yaml 추가 의존성
dependencies:
  path_provider: ^2.1.0          # 모델 파일 저장 경로
  crypto: ^3.0.3                 # SHA-256 체크섬 검증
  sqflite: ^2.3.0                # 로컬 태스크 큐 (오프라인 결과 보관)
  connectivity_plus: ^6.0.0      # 기존 — 네트워크 상태 감지
  dio: ^5.9.0                    # 기존 — 모델 다운로드 재사용
```

---

## 6. 의존성 (Dependencies)

### 선행 SPEC

| SPEC | 상태 | 관계 |
|------|------|------|
| SPEC-MOBILE-001 | completed | Flutter 모바일 기반 구조, Push 알림, 백그라운드 녹음 |
| SPEC-APP-001 | completed | Flutter 클라이언트 기본 구조, 녹음 기능 |
| SPEC-STT-001 | completed | 백엔드 STT 파이프라인 (whisper-large-v3) |
| SPEC-SSE-001 | completed | 실시간 상태 업데이트 (SSE + 폴링) |
| SPEC-APP-002 | completed | ConnectivityService, OfflineBanner, PipelineProvider |

### 참조 파일

| 파일 | 경로 | 용도 |
|------|------|------|
| STT 엔진 | `backend/ml/stt_engine.py` | 백엔드 플랫폼 적응형 Whisper 구현 참조 |
| 파이프라인 프로바이더 | `client/lib/providers/pipeline_provider.dart` | 기존 SSE+폴링 파이프라인 흐름 |
| 오디오 API | `client/lib/services/audio_api.dart` | 오디오 업로드/스트리밍 기존 구현 |
| 연결 서비스 | `client/lib/services/connectivity_service.dart` | 네트워크 상태 감지 기존 구현 |
| 녹음 서비스 | `client/lib/services/recording_service.dart` | 백그라운드 녹음 기존 구현 |
| 푸시 서비스 | `backend/app/services/push_service.py` | Celery 훅 기반 Push 알림 |

---

*SPEC ID: SPEC-MOBILE-002*
*생성일: 2026-06-10*
*상태: draft*
