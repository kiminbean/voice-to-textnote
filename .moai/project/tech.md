# Voice to TextNote - 기술 스택 및 아키텍처

## 기술 스택 개요

### STT 백엔드 계층 (완료 ✅)

**Web Framework**: FastAPI 0.135+
- 비동기 웹 프레임워크로 높은 동시성 지원
- Pydantic v2로 강력한 입력 검증
- 자동 OpenAPI/Swagger 문서 생성

**STT 처리**: mlx-whisper 0.4+
- Whisper Large-v3-Turbo 모델 (WER < 5%)
- Apple Silicon MPS 가속
- 로컬 처리로 프라이버시 보장

**비동기 작업**: Celery 5.6+ + Redis 7.0+
- Celery: 백그라운드 STT 처리
- Redis: 메시지 브로커 + 결과 캐시 (24시간 TTL)

**오디오 처리**: pydub 0.25.1+
- ffmpeg 래핑으로 다양한 형식 지원
- 16kHz 모노 WAV 변환
- 음량 정규화

**데이터 검증**: Pydantic 2.9+
- 요청/응답 자동 검증
- 파일 형식, 크기, 재생 시간 검증

**문서 파싱**:
- **python-docx** 0.8.11+: DOCX 문서에서 문단, 표, 스타일 추출
- **pdfplumber** 0.10+: PDF에서 텍스트, 표 추출 및 폰트 크기 기반 섹션 감지

**로깅**: structlog 24.0+
- 구조화된 JSON 로그 생성
- 운영 환경에서 로그 분석 용이

**테스트**: pytest 8.0+
- 716개 단위/통합/E2E 테스트 (STT 150 + DIA 88 + MIN 71 + SUM 68 + TMPL 78 + E2E 16)
- 90.4% 코드 커버리지

---

### 클라이언트 계층

**Framework**: Flutter 3.24+
- **이유**: 단일 코드베이스로 웹, iOS, Android, macOS 지원
- **장점**: Dart 언어의 타입 안전성, hot reload로 빠른 개발 속도, 풍부한 위젯 라이브러리
- **버전**: Null Safety 완전 지원
- **지원 플랫폼**: Web (Chromium), iOS 12+, Android 8+, macOS 10.15+

**상태관리**: Riverpod 2.4.0+
- **이유**: 의존성 주입과 상태관리를 통합
- **장점**: 테스트 용이, 코드 제네레이션으로 타입 안전성
- **사용 예**: 회의 목록, 녹음 상태, 전사 결과

**HTTP 클라이언트**: Dio 5.3.0+
- **이유**: 강력한 요청/응답 인터셉터 기능
- **기능**: 요청 타임아웃, 자동 재시도, 요청 로깅

**로컬 저장소**: Hive 2.2.0+ 또는 SQLite 2.3.0+
- **Hive**: NoSQL 로컬 저장소, 빠른 속도
- **SQLite**: 관계형 데이터 저장
- **선택**: 프로토타입은 Hive, 복잡한 쿼리는 SQLite

**오디오 녹음**: record 4.4.0+ (또는 audio_session)
- **이유**: 크로스 플랫폼 오디오 녹음 API
- **기능**: 실시간 음량 계측, 일시 중지/재개 기능
- **포맷**: WAV, MP4, AAC 지원

**파일 선택**: file_picker 6.1.0+
- **이유**: 크로스 플랫폼 파일 선택 다이얼로그 (PDF/DOCX)
- **기능**: iOS, Android, Web, macOS에서 일관된 파일 선택 UI 제공

**파형 시각화**: audio_waveforms 1.1.0+
- **이유**: 실시간 오디오 파형을 효율적으로 렌더링
- **성능**: 60fps 유지

**다국어 지원**: intl 0.19.0+, flutter_localizations
- **지원 언어**: 한국어, 영어, 일본어
- **패턴**: ARB (Application Resource Bundle) 파일 사용

**네비게이션**: go_router 13.0.0+
- **이유**: 선언적 라우팅, Deep linking 지원
- **기능**: 인자 전달, 중첩 네비게이션

**실시간 업데이트 & UI**:
- **shimmer** (로딩 인디케이터): 데이터 로딩 중 시각적 피드백
- **connectivity_plus** (네트워크 감지): 온/오프라인 상태 감지
- **SSE 클라이언트**: 서버 실시간 이벤트 수신

---

### 백엔드 계층

**Web Framework**: FastAPI 0.109+
- **이유**: 비동기 처리로 높은 처리량, 자동 OpenAPI 문서 생성
- **Python 버전**: 3.11 이상 필수 (f-string, 타입 힌팅 최신 기능)
- **장점**: 타입 안전성, 빠른 개발 속도, 내장 데이터 검증(Pydantic)
- **성능**: uvicorn으로 평균 1,000 RPS 처리 가능

**데이터베이스 ORM**: SQLAlchemy 2.0+
- **이유**: 강력한 ORM, 여러 DB 벤더 지원
- **사용 DB**: PostgreSQL 15+ (프로덕션), SQLite (개발)
- **마이그레이션**: Alembic 으로 스키마 버전 관리

**비동기 작업 큐**: Celery 5.3+
- **Broker**: Redis 7.0+
- **이유**: 긴 작업(STT, Diarization)을 백그라운드에서 비동기 처리
- **작업 종류**:
  - `transcription_task`: STT 처리 (평균 30초~5분)
  - `diarization_task`: 스피커 식별 (평균 20초~3분)
  - `summary_task`: AI 요약 생성 (평균 10초~1분)
- **모니터링**: Flower로 작업 모니터링

**캐싱**: Redis 7.0+
- **용도**: 결과 캐싱, 세션 저장, 레이트 리미팅
- **TTL**: 회의 결과는 24시간, 임시 캐시는 1시간

**인증**: python-jose + passlib
- **JWT**: Bearer 토큰 기반 인증
- **암호화**: bcrypt로 비밀번호 해싱 (cost=12)
- **API Key**: 조직별 고유 API 키 관리

**데이터 검증**: Pydantic v2
- **이유**: 요청/응답 자동 검증, IDE 자동완성
- **예시**: 오디오 업로드 크기 검증(최대 500MB), 형식 검증(WAV, MP3, M4A)

**로깅**: python-json-logger
- **포맷**: JSON 형식으로 구조화된 로깅
- **레벨**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **저장소**: 파일시스템 또는 ELK 스택

**보안 & 모니터링**:
- **slowapi** (레이트 리미팅): IP당 분당 요청 제한
- **prometheus-fastapi-instrumentator** (메트릭): FastAPI 메트릭 자동 수집
- **prometheus-client** (Prometheus 클라이언트): 커스텀 메트릭 정의
- **sse-starlette** (실시간 스트리밍): Server-Sent Events 구현

**데이터 영속성**:
- **SQLAlchemy 2.0** (비동기 ORM): asyncpg + aiosqlite 지원
- **asyncpg** (비동기 PostgreSQL): 고성능 비동기 데이터베이스
- **aiosqlite** (비동기 SQLite): 개발 환경용
- **Alembic** (마이그레이션): 스키마 버전 관리

**시스템 모니터링**:
- **psutil** (리소스 모니터링): CPU, 메모리, 디스크 사용량 추적

**테스팅**: pytest 7.4+
- **커버리지**: 96.94% (타겟: 최소 85%)
- **테스트 수**: 767개 (백엔드 700개 + Flutter 67개)
- **유형**:
  - **단위 테스트**: 개별 함수 테스트
  - **통합 테스트**: API 엔드포인트 테스트
  - **E2E 테스트**: 전체 녹음~요약 파이프라인 테스트

---

### 음성 처리 (STT/Diarization)

**STT (Speech-to-Text)**: mlx-whisper (Whisper Large-v3-Turbo)
- **모델**: OpenAI Whisper Large-v3-Turbo
- **크기**: ~3GB
- **언어**: 99개 언어 지원 (한국어 포함)
- **정확도**: WER(Word Error Rate) < 5% (한국어)
- **속도**:
  - 실시간 인자: 0.3~0.5배 (1시간 녹음 처리에 20~30분)
  - M4 Mac Mini에서 최적화
- **왜 mlx-whisper?**
  - Apple Silicon MPS 완전 지원으로 GPU 처리
  - 로컬 전용 처리로 프라이버시 보호
  - 오픈소스로 무료 사용

**Diarization (스피커 식별)**: pyannote.audio 3.1
- **모델**: Segmentation + Speaker Embedding
- **CPU 기반**: GPU 미사용으로 안정성 우선
- **성능**:
  - Diarization Error Rate: < 15% (5명 이하 회의)
  - 처리 시간: 녹음 시간의 0.5~1배
- **출력**: [(start_time, end_time, speaker_id), ...]
- **왜 CPU?**
  - 안정성: GPU 메모리 부족 리스크 없음
  - 비용: GPU 서버 불필요
  - 재현성: 동일한 하드웨어로 일관된 결과

**설정**:

```yaml
# ml/whisper_config.py
WHISPER_MODEL = "whisper-large-v3-turbo"
WHISPER_DEVICE = "mps"  # Apple Silicon에서 Metal Performance Shader
WHISPER_COMPUTE_TYPE = "float16"  # 정밀도 설정
LANGUAGE = "ko"  # 한국어로 고정 또는 자동 감지

# ml/pyannote_config.py
SEGMENTATION_THRESHOLD = 0.5
MIN_DURATION_ON = 0.097
MIN_DURATION_OFF = 0.097
NUM_SPEAKERS = None  # 스피커 수 자동 추정
```

### 음성 톤/운율 분석
- **opensmile** ^2.6.0: eGeMAPSv02 88차원 감정 특화 음향 특징 추출 (AGPL-3.0, 로컬 전용)
- **librosa** ^0.10.0: F0(pYIN), RMS energy, speaking rate 계산 (ISC)

---

### AI 기반 처리

**LLM**: Claude 3.5 Sonnet (Anthropic Claude API)
- **용도**: 회의 요약, 액션 아이템 추출, 텍스트 정렬
- **API 버전**: claude-3-5-sonnet-20241022
- **요청 형식**:
  ```json
  {
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": "다음 회의록을 정리하고 주요 결정사항을 추출해주세요:\n[전사본]"
      }
    ]
  }
  ```
- **비용**: 요청 토큰 $3/백만, 응답 토큰 $15/백만
- **응답 시간**: 평균 2~5초

---

### 인프라 및 배포

**서버 구성**: Ubuntu 24.04 + systemd 서비스
- **프로세스 관리**: systemd (voicenote-api, voicenote-worker)
- **메시지 브로커**: Redis (시스템 패키지, systemd 관리)
- **데이터베이스**: SQLite (개발) / PostgreSQL (프로덕션)
- **STT 엔진**: 플랫폼 자동 감지
  - macOS: mlx_whisper (Apple Silicon 가속)
  - Linux: openai-whisper (CPU/CUDA)

**원격 접속**: Tailscale VPN 메시
- 서버/클라이언트에 Tailscale 설치
- 고정 IP 부여, 포트 개방 불필요
- 아이폰에서 Tailscale IP로 접속

**배포 스크립트**: `deploy/setup-ubuntu.sh`
- Redis, FFmpeg, Python venv 자동 설치
- systemd 서비스 자동 등록
- .env 템플릿 자동 생성

**CI/CD**: GitHub Actions
- **Trigger**:
  - Pull Request 생성/업데이트
  - main 브랜치로 merge
- **파이프라인**:
  1. 백엔드 단위 테스트 및 커버리지 검사 (96.94% 달성)
  2. 프론트엔드 빌드 및 정적 분석
  3. 통합 테스트 (전체 스택)
  4. Dependabot 의존성 관리

**배포 환경**:
- **개발**: macOS (M1 MacBook Pro, mlx-whisper)
- **프로덕션**: Ubuntu 24.04 PC (systemd + Redis + openai-whisper)
- **클라이언트**: Flutter iOS 앱 (Tailscale로 서버 접속)

---

## 아키텍처 개요

### 3계층 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                       프레젠테이션 계층                        │
│  Flutter Web/iOS/Android/macOS - Riverpod 상태관리 - Dio   │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
┌────────────────────────▼────────────────────────────────────┐
│                      비즈니스 로직 계층                        │
│       FastAPI (uvicorn) - 라우터, 서비스, 검증                │
│  - 오디오 업로드 처리                                         │
│  - 작업 진행 상황 추적                                        │
│  - 요청 검증 및 에러 처리                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼─────┐  ┌──────▼──────┐  ┌────▼──────────┐
│   데이터계층 │  │ 작업큐      │  │ 캐싱계층      │
├─────────────┤  ├─────────────┤  ├───────────────┤
│PostgreSQL   │  │ Celery +    │  │ Redis         │
│(영구 저장)   │  │ Redis       │  │ (임시 저장)    │
└──────┬──────┘  └──────┬──────┘  └───────────────┘
       │                │
       │    ┌───────────┼───────────┐
       │    │           │           │
       └────┴──────┬────┼──┬────┬───┼────┐
                   │    │  │    │   │    │
            ┌──────▼─┐ ┌▼─▼──┐ ┌─┴─┐ │    │
            │파일저장│ │STT  │ │구분│ │모니│
            │시스템  │ │워커 │ │화  │ │터 │
            │(로컬)  │ │     │ │워커│ │    │
            └────────┘ └──────┘ └────┘ │    │
                                ┌──────▼──┐
                                │요약워커  │
                                │(Claude) │
                                └─────────┘
```

### 데이터 흐름

```
1. 클라이언트 녹음 시작
   ↓
2. Flutter 앱이 오디오 스트림 캡처 (WAV 형식)
   ↓
3. FastAPI로 POST /api/v1/audio/upload
   ↓
4. 서버가 파일 저장 및 Meeting 레코드 생성
   ↓
5. Celery 작업 체인 시작:
   a) transcription_task: mlx-whisper로 음성→텍스트 (30초~5분)
   b) diarization_task: pyannote로 스피커 식별 (20초~3분)
   c) summary_task: Claude API로 요약 생성 (10초~1분)
   ↓
6. Redis 캐시에 중간 결과 저장
   ↓
7. PostgreSQL에 최종 결과 저장
   ↓
8. 클라이언트가 GET /api/v1/meetings/{id} 폴링으로 진행 상황 확인
   ↓
9. 완료 시 회의록 표시
```

### 성능 특성

**처리 시간 (M4 Mac Mini 24GB 기준)**:
- STT (1시간 음성): 20~30분
- Diarization (1시간 음성): 15~25분
- 요약 생성: 10~20초

**메모리 사용**:
- mlx-whisper: ~6GB
- pyannote: ~4GB
- FastAPI + Redis: ~2GB
- 총합: ~12GB (24GB 충분)

**동시 처리 능력**:
- FastAPI API 서버: 최대 100 동시 연결
- Celery 워커: CPU 코어수만큼 병렬 처리 (M4 Mac Mini = 10코어)
- 따라서 동시에 최대 10개의 음성 파일 처리 가능

---

## 왜 이 기술 스택을 선택했는가?

### Flutter (클라이언트)

| 대안 | 비교 |
|------|------|
| React Native | 성능 더 낮음, Dart 타입 안전성 우수 |
| SwiftUI + Kotlin | 코드 중복, 유지보수 어려움 |
| Electron | 메모리 사용량 많음, 모바일 미지원 |
| **Flutter** | **최고 성능, 단일 코드베이스, 풍부한 위젯** |

### FastAPI (백엔드)

| 대안 | 비교 |
|------|------|
| Django | 무겁고 느림, 비동기 처리 약함 |
| Flask | 소규모 프로젝트용, 자동 문서화 없음 |
| Express.js | JavaScript 약한 타입 안전성 |
| **FastAPI** | **빠르고 가볍고 강한 타입 안전성** |

### mlx-whisper (STT)

| 대안 | 비교 |
|------|------|
| Google Cloud Speech | 클라우드 비용 높음, 프라이버시 문제 |
| Azure Cognitive Services | 마찬가지로 클라우드 기반 |
| Vosk (로컬) | 정확도 낮음 (WER > 20%) |
| **mlx-whisper** | **높은 정확도, 로컬 처리, Apple Silicon 최적화** |

### pyannote.audio (Diarization)

| 대안 | 비교 |
|------|------|
| Google Cloud Diarization | 클라우드 비용 높음 |
| UIS-RNN | 설정 복잡, 정확도 낮음 |
| wav2vec2 기반 커스텀 | 학습 데이터 필요 |
| **pyannote.audio** | **SOTA 모델, 사용 간단, 정확도 우수** |

### PostgreSQL (데이터베이스)

| 대안 | 비교 |
|------|------|
| MySQL | 트랜잭션 안정성 낮음 |
| MongoDB | 관계형 데이터에 부적합 |
| SQLite | 동시성 처리 약함 |
| **PostgreSQL** | **안정성, 동시성, 확장성 우수** |

---

## 개발 환경 요구사항

### 로컬 머신

- **운영체제**: macOS 12+ (M1/M2/M3/M4 Apple Silicon)
- **RAM**: 최소 16GB, 권장 24GB 이상
- **SSD**: 최소 50GB 여유공간 (모델 파일 ~6GB, 오디오 저장소 용도)

### 필수 소프트웨어

**Python 환경**:
- Python 3.11 이상
- pip 또는 poetry (의존성 관리)
- Homebrew (macOS 패키지 관리)

**설치 명령**:
```bash
# Homebrew 설치 (미설치 시)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.11 설치
brew install python@3.11

# 다른 필수 도구
brew install postgresql redis git
```

**Flutter 환경**:
- Flutter SDK 3.24+
- Dart SDK (Flutter에 포함)
- XCode 15+ (iOS 개발)
- Android SDK (Android 개발, Android Studio 설치 권장)

**설치 명령**:
```bash
# Flutter SDK 설치
git clone https://github.com/flutter/flutter.git ~/flutter
export PATH="$PATH:$HOME/flutter/bin"
flutter doctor  # 환경 검사

# XCode 설치 (App Store에서)
xcode-select --install
```

---

## 빌드 및 배포 절차

### 개발 환경 설정 (macOS)

```bash
# 1. 저장소 클론
git clone https://github.com/kiminbean/voice-to-textnote.git
cd voice-to-textnote

# 2. 백엔드 환경 설정
python -m venv venv
source venv/bin/activate
pip install -r deploy/requirements-ubuntu.txt  # 또는 mlx-whisper (macOS)

# 3. Redis 시작
brew install redis
brew services start redis

# 4. .env 설정
cp .env.example .env
nano .env

# 5. 백엔드 서버 시작
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 6. Celery 워커 시작 (별도 터미널)
celery -A backend.workers.celery_app:celery_app worker --loglevel=info

# 7. 클라이언트 시작 (별도 터미널)
cd client
flutter pub get
flutter run -d chrome
```

### 프로덕션 배포 (Ubuntu 24.04)

```bash
# 원클릭 설치 (Redis, Python, systemd 서비스 자동 설정)
git clone https://github.com/kiminbean/voice-to-textnote.git
cd voice-to-textnote
bash deploy/setup-ubuntu.sh

# .env 설정
nano .env

# 서비스 시작
sudo systemctl start voicenote-api voicenote-worker

# 상태 확인
sudo systemctl status voicenote-api
curl http://localhost:8000/api/v1/health
```

### 외부 접속 (Tailscale)

```bash
# 서버에 Tailscale 설치 후 고정 IP로 접속
# 아이폰에서: http://100.x.x.x:8000/api/v1
```

---

## 주요 통합 지점

### Claude API 통합

```python
# ml/claude_summarizer.py
from anthropic import Anthropic

client = Anthropic()

def generate_summary(transcript: str, speakers: List[str]) -> Dict:
    """회의록 요약 생성"""
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""
            다음은 팀 회의의 전사본입니다.

            참석자: {', '.join(speakers)}

            전사:
            {transcript}

            다음을 정리해주세요:
            1. 주요 결정사항
            2. 액션 아이템 (담당자, 마감일 포함)
            3. 논의 내용 요약

            JSON 형식으로 응답해주세요.
            """
        }]
    )

    return parse_response(response.content[0].text)
```

### Celery 작업 오케스트레이션

```python
# workers/tasks/orchestrator.py
from celery import chain, group

def process_meeting(audio_file_path: str, meeting_id: str):
    """전체 처리 파이프라인"""
    pipeline = chain(
        transcription_task.s(audio_file_path),
        diarization_task.s(audio_file_path),
        summary_task.s()  # 결과를 다음 태스크로 전달
    )

    result = pipeline.apply_async(
        kwargs={'meeting_id': meeting_id},
        queue='default'
    )

    return result.id
```

---

## 성능 모니터링

### 메트릭 수집

**Prometheus** (메트릭 저장):
- FastAPI 요청 수, 응답 시간
- Celery 작업 완료 시간, 실패율
- Redis 메모리 사용량, 캐시 히트율

**Grafana** (시각화):
- 대시보드: API 성능, 작업 큐 상태, 시스템 리소스

### 로깅

**CloudWatch 또는 ELK Stack**:
- 모든 API 요청/응답 로깅
- 에러 및 예외 추적
- Celery 작업 로그

---

## 보안 고려사항

### 데이터 보안

- **전송 암호화**: 모든 HTTP 통신을 HTTPS로 강제
- **저장 암호화**: 선택적 AES-256 암호화 (민감한 조직용)
- **접근 제어**: JWT 토큰 기반 API 인증, RBAC(역할 기반 접근 제어)

### API 보안

- **레이트 리미팅**: IP당 분당 60개 요청 제한
- **입력 검증**: Pydantic으로 모든 입력 검증
- **CORS**: 등록된 도메인만 허용
- **CSRF**: Starlette 미들웨어로 보호

### 인프라 보안

- **방화벽**: 22(SSH), 443(HTTPS), 5432(PostgreSQL 내부만) 포트만 개방
- **로그 감시**: 비정상 접근 시도 모니터링
- **정기 보안 업데이트**: 의존성 취약점 자동 스캔 (Dependabot)

---

## 확장성 계획

### 단계별 확장

**Phase 1** (초기): 단일 서버 (M4 Mac Mini)
- 동시 회의: 최대 10개
- 월 회의 건수: ~1,000건

**Phase 2** (중기): 다중 서버 로드 밸런싱
- 서버 수: 3~5개 (스케일 아웃)
- 동시 회의: 최대 50개
- 월 회의 건수: ~10,000건

**Phase 3** (장기): Kubernetes 오케스트레이션
- 자동 스케일링으로 트래픽 변동 대응
- 월 회의 건수: 100,000건 이상

---

## 마이그레이션 가능성

### 클라우드 이전 시나리오

현재 로컬 환경에서 AWS로 이전 시:

1. **RDS**: 로컬 PostgreSQL → AWS RDS PostgreSQL
2. **ElastiCache**: 로컬 Redis → AWS ElastiCache Redis
3. **EC2**: M4 Mac Mini → AWS c6i 또는 c7i (CPU 기반)
4. **S3**: 로컬 파일 시스템 → AWS S3
5. **Auto Scaling**: 고정 인스턴스 → ASG로 자동 확장

예상 월 비용: $500~1,000 (500~1000건 회의 처리)

---

## 기술 부채 방지

### 의존성 관리

- **Poetry** (Python): 자동 버전 락, 재현성 보장
- **pubspec.lock** (Flutter): 의존성 버전 고정
- **정기 업데이트**: 월 1회 의존성 보안 업데이트 검토

### 코드 품질

- **Linting**: ruff, black (Python), analysis_options.yaml (Dart)
- **테스트 커버리지**: 최소 85% 유지
- **CI/CD**: PR 승인 전 자동 테스트 실행

### 문서화

- **API 문서**: Swagger/OpenAPI 자동 생성
- **코드 주석**: 함수마다 docstring 작성
- **아키텍처 문서**: 주요 결정사항 기록

이 기술 스택으로 안정적이고 확장 가능한 시스템을 구축할 수 있습니다.
