# Voice to TextNote - 아키텍처 개요

> 이 문서는 신규 프로젝트의 목표 아키텍처를 기술합니다. 코드 구현 후 `/moai codemaps` 명령으로 실제 코드베이스 기반 아키텍처 문서를 생성하세요.

## 시스템 아키텍처

```
[Flutter 클라이언트]
Web / iOS / Android / macOS
        |
        | REST API / WebSocket
        v
[FastAPI 백엔드 서버]
        |
    +---+---+
    |       |
    v       v
[Celery    [Redis]
 Worker]   메시지 브로커 / 캐시
    |
    +---+---+
    |       |
    v       v
[mlx-whisper]  [pyannote.audio]
 STT 처리       화자 분리
    |
    v
[Claude API]
 회의록 요약 / 정리
```

## 주요 컴포넌트

| 컴포넌트 | 역할 | 기술 |
|---------|------|------|
| Flutter 클라이언트 | 크로스 플랫폼 UI (Web/iOS/Android/macOS) | Flutter 3.x, Dart |
| FastAPI 서버 | REST API 엔드포인트, 인증, 파일 업로드 | Python, FastAPI |
| Celery 워커 | 비동기 오디오 처리 작업 큐 | Celery, Python |
| Redis | 메시지 브로커, 작업 상태 캐시 | Redis |
| mlx-whisper | 로컬 음성 인식 (M4 Mac Mini) | Python, mlx-whisper |
| pyannote.audio | 화자 분리 | Python, pyannote |
| Claude API | 회의록 요약 및 AI 후처리 | Anthropic Claude API |

## 데이터 흐름

1. 사용자가 Flutter 앱에서 회의 녹음 시작
2. 오디오 파일이 FastAPI 서버로 업로드
3. Celery 워커가 비동기로 처리 작업 수신
4. mlx-whisper로 텍스트 변환 수행
5. pyannote.audio로 화자 분리 실행
6. Claude API로 회의록 요약 생성
7. 결과가 클라이언트로 반환

## 프라이버시 설계

- 모든 처리는 로컬 M4 Mac Mini에서 수행
- 클라우드 STT 서비스 미사용
- Claude API만 외부 연결 (선택 사항)
- 오디오 데이터 외부 전송 없음
