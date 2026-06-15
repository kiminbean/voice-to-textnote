# Voice to TextNote - 제품 개요

## 프로젝트명 및 슬로건

**Voice to TextNote** - 일상적인 팀 회의를 자동으로 기록하고 정리하는 개인정보 보호형 회의록 자동화 도구

## 문제 정의

### 현재의 문제점

- **수동 기록의 시간 소모**: 팀원들이 회의 중 수동으로 노트를 작성하면 회의 내용에 집중하기 어려움
- **기록의 정확성 부족**: 수동 기록은 누락, 오류, 편견이 발생하기 쉬움
- **후처리 작업 부담**: 회의 후 기록을 정리하고 형식을 맞추는데 추가 시간 소요
- **클라우드 서비스의 제약**: 민감한 팀 내용을 외부 클라우드에 업로드하기 꺼려함
- **스피커 식별 어려움**: 누가 언제 무엇을 말했는지 자동으로 파악하기 어려움

## 대상 사용자

- **소규모 팀**: 5-20명 규모의 스타트업, 프로젝트팀
- **일일 스탠드업 진행 팀**: 매일 아침 정기적으로 회의를 진행하는 조직
- **프라이버시 민감 조직**: 회의 내용을 외부 클라우드에 보관하고 싶지 않은 팀
- **분산 팀**: 원격 근무 팀원들의 회의 기록이 필요한 경우

### 사용자 특성

- 기술에 익숙한 개발팀, PM, 데이터 팀
- 효율성을 중시하는 조직 문화
- 프라이버시와 데이터 보안을 우선순위로 생각하는 기업

## 핵심 기능

### 1. 음성-텍스트 변환 (STT) 백엔드 (SPEC-STT-001 ✅)

- **음성 인식 API**: FastAPI 기반 RESTful API로 오디오 업로드 및 STT 처리
- **mlx-whisper 통합**: Apple Silicon MPS 가속을 활용한 고정확도 음성 인식
- **비동기 처리**: Celery 작업 큐로 백그라운드 STT 처리
- **Redis 캐싱**: 24시간 TTL로 처리 결과 빠른 재조회
- **헬스체크 API**: 서비스, Redis, Celery 상태 모니터링

### 2. 화자 분리 (Diarization) 백엔드 (SPEC-DIA-001 ✅)

- **화자 분리 API**: pyannote.audio 3.1 기반 Speaker Diarization 파이프라인
- **타임스탬프 매칭**: STT 세그먼트와 화자 분리 결과를 overlap 기반으로 정밀 매칭
- **비동기 처리**: Celery 태스크로 백그라운드 화자 분리 (동시 2개 제한)
- **상태 추적**: pending → processing → completed 상태 전이 및 진행률 추적
- **헬스체크**: 모델 로드 상태, 메모리 사용량 모니터링
- **메모리 보호**: 24GB의 80% 초과 시 신규 작업 거부 (503)

### 3. 회의록 생성 백엔드 (SPEC-MIN-001 ✅)

- **회의록 API**: DIA 결과를 입력으로 화자별 회의록 자동 생성
- **세그먼트 병합**: 연속 동일 화자 발화를 하나의 블록으로 병합
- **화자 통계**: 화자별 발화 시간, 횟수, 비율 자동 계산
- **다형식 출력**: JSON 및 Markdown 형식 지원
- **커스텀 화자 이름**: 사용자 정의 화자 이름 매핑 지원
- **비동기 처리**: Celery 태스크 (동시 3개 제한)

### 4. AI 회의 요약 백엔드 (SPEC-SUM-001 ✅)

- **OpenAI gpt-4o-mini 통합**: 회의록을 OpenAI API에 전송하여 자동 요약 생성
- **액션 아이템 추출**: 회의 중 결정된 할당 업무를 구조화된 형태로 추출 (assignee, task, deadline, priority)
- **결정사항/다음 단계**: 핵심 결정사항과 후속 작업을 자동 식별
- **Graceful Fallback**: API 응답 파싱 실패 시 원문 텍스트로 안전하게 대체
- **비동기 처리**: Celery 태스크 (동시 2개 제한, API 비용 관리)

### 5. Flutter 클라이언트 MVP (SPEC-APP-001 ✅)

- **크로스 플랫폼 앱**: Flutter 기반 Web + macOS 지원
- **API 연동**: 백엔드 4개 파이프라인(STT/DIA/MIN/SUM) 전체 연동 (Dio)
- **상태 관리**: Riverpod (녹음/파이프라인/회의 목록)
- **자동 파이프라인**: 녹음 완료 → 업로드 → STT → 화자분리 → 회의록 → AI요약 자동 진행
- **4개 화면**: 홈(회의 목록), 녹음, 처리 상태, 결과(회의록+요약+액션 아이템)
- **오디오 녹음**: record 패키지, WAV 형식, macOS 마이크 권한 설정

### 6. API 보안 (SPEC-SEC-001 ✅)

- **API Key 인증**: Bearer token 기반 API 키 검증
- **레이트 리미팅**: slowapi로 IP당 분당 요청 수 제한
- **CORS 정책**: 등록된 도메인만 허용
- **Security Headers**: HSTS, X-Content-Type-Options, X-Frame-Options 등 자동 설정
- **입력 검증**: Pydantic으로 모든 요청 검증

### 7. 모니터링 & 메트릭 (SPEC-INFRA-001 ✅)

- **Prometheus 통합**: FastAPI 메트릭 자동 수집 (prometheus-fastapi-instrumentator)
- **요청 ID 추적**: 모든 요청에 고유 ID 부여로 추적 가능
- **/metrics 엔드포인트**: Prometheus 형식의 메트릭 노출
- **Readiness 프로브**: /ready 엔드포인트로 헬스 상태 확인
- **구조화된 로깅**: JSON 형식의 요청/응답 로깅

### 8. 에러 처리 (SPEC-ERR-001 ✅)

- **전역 예외 처리**: 모든 API 에러를 표준화된 응답으로 반환
- **사용자 친화적 메시지**: 기술 정보는 숨기고 명확한 오류 메시지 제공
- **재시도 로직**: 임시 오류는 자동 재시도
- **폴백 메커니즘**: 외부 API 실패 시 안전한 대체 방안 제공
- **에러 로깅**: 모든 에러 발생 상황 상세 기록

### 9. 감사 로깅 (SPEC-LOG-001 ✅)

- **요청/응답 로깅**: 모든 API 호출에 대한 상세 로깅
- **사용자 추적**: API 키로 사용자 행동 추적
- **타임스탬프**: 모든 로그에 정확한 시각 기록
- **JSON 포맷**: 로그 분석 및 검색 용이
- **보안 정보 제외**: 민감한 정보는 마스킹

### 10. 서버 배포 (SPEC-DEPLOY-001 ✅)

- **Ubuntu systemd 서비스**: voicenote-api, voicenote-worker 자동 관리
- **원클릭 배포 스크립트**: deploy/setup-ubuntu.sh (Redis, Python, systemd 자동 설정)
- **듀얼 STT 백엔드**: macOS(mlx_whisper) + Linux(openai-whisper) 자동 감지
- **환경 분리**: 개발(SQLite) / 프로덕션(PostgreSQL) 설정 분리
- **Tailscale 원격 접속**: VPN 메시로 포트 개방 없이 외부 접속

### 11. PostgreSQL 데이터베이스 (SPEC-DB-001 ✅)

- **비동기 SQLAlchemy 2.0**: asyncpg로 비동기 데이터베이스 접근
- **Alembic 마이그레이션**: 스키마 버전 관리 자동화
- **데이터 영속성**: 회의록, 사용자, 작업 이력 저장
- **트랜잭션 안정성**: ACID 준수로 데이터 무결성 보장
- **동기 엔진**: 테스트 환경에서 SQLite 사용

### 12. SSE 실시간 스트리밍 (SPEC-SSE-001 ✅)

- **서버-전송 이벤트**: sse-starlette로 실시간 푸시 알림
- **진행률 업데이트**: 회의 처리 진행 상황 실시간 전송
- **연결 관리**: 자동 재연결 및 하트비트
- **다중 클라이언트**: 같은 회의 ID에 대해 여러 클라이언트 지원

### 13. 데이터 지속성 통합 (SPEC-PERSIST-001 ✅)

- **자동 저장**: 작업 생성 시 즉시 DB에 저장
- **API 폴백**: 네트워크 오류 시 로컬 캐시 사용
- **동기화**: 연결 복구 시 자동 동기화
- **데이터 무결성**: 중복 저장 방지 및 일관성 유지

### 14. 앱 라이프사이클 (SPEC-LIFECYCLE-001 ✅)

- **시작 검증**: 모델 로드, DB 연결, Redis 확인
- **Graceful Shutdown**: 진행 중인 작업 완료 후 종료
- **헬스 프로브**: Kubernetes 배포 시 자동 재시작
- **메모리 모니터링**: psutil로 리소스 사용량 추적

### 15. 회의 이력 API (SPEC-HISTORY-001 ✅)

- **페이지네이션**: 회의 목록 분할 조회 (limit, offset)
- **필터링**: 날짜, 사용자, 상태별 조회
- **정렬**: 생성일, 수정일 기준 정렬
- **메타데이터**: 각 회의의 통계 정보 포함
- **벌크 조회**: 여러 회의 동시 조회

### 16. 데이터 보유 정책 (SPEC-RETENTION-001 ✅)

- **30일 DB 보유**: PostgreSQL에서 30일 후 자동 삭제
- **24시간 임시 파일**: /tmp의 오디오 파일 24시간 후 자동 정리
- **Celery Beat**: 정기 작업으로 자동 정리 실행
- **보관 정책**: 특정 회의는 수동 보관 가능
- **감사 로그**: 삭제 이력은 영구 보관

### 17. E2E 통합 테스트 (SPEC-E2E-001 ✅)

- **전체 파이프라인 테스트**: 녹음→업로드→STT→DIA→MIN→SUM까지 전체 검증
- **767개 테스트**: 백엔드 700개, Flutter 67개
- **96.94% 커버리지**: 핵심 기능 전면 검증
- **실시간 진행률 추적**: 각 단계별 상태 확인
- **결과 검증**: 최종 출력의 정확성 확인

### 18. Flutter 기능 강화 (SPEC-APP-002 ✅)

- **SSE 실시간 스트리밍**: 서버에서 실시간 진행률 수신
- **오류 처리 UI**: 사용자 친화적인 오류 메시지 표시
- **Shimmer 로딩**: 데이터 로딩 중 시각적 피드백
- **데이터 바인딩**: Riverpod로 자동 UI 업데이트
- **Connectivity 감지**: 네트워크 상태 실시간 감지

### 19. CI/CD 파이프라인 (SPEC-CI/CD와 통합)

- **GitHub Actions**: Pull Request 및 main 브랜치 자동 테스트
- **테스트 자동화**: 커버리지 검사 및 린트 검사
- **배포 스크립트**: Ubuntu systemd 서비스 자동 배포
- **의존성 관리**: Dependabot으로 보안 업데이트 자동화

### 20. 회의록 양식 관리 (SPEC-TMPL-001 ✅)

- **양식 업로드 API**: PDF/DOCX 파일 업로드 및 구조 추출
- **구조 자동 추출**: python-docx와 pdfplumber를 활용한 섹션/표/필드 자동 추출
- **양식 기반 AI 프롬프트**: 추출된 양식 구조를 AI 프롬프트에 주입하여 커스텀 회의록 생성
- **Flutter 양식 관리 화면**: 양식 업로드, 목록, 삭제 기능 제공
- **하위 호환성**: 양식을 선택하지 않으면 기본 4개 항목(summary_text, action_items, key_decisions, next_steps)으로 회의록 생성

### 21. 장시간 녹음 안정성 (SPEC-PERF-001 ✅)

- **화자 분리 청크 분할**: 15분 초과 오디오를 10분 단위로 분할하여 CPU 서버에서도 안정 처리
- **Redis visibility_timeout 설정**: 장시간 Celery 작업의 중복 실행 방지 (7200초)
- **SoftTimeLimitExceeded 처리**: 60분 초과 시 graceful 실패 처리
- **Flutter 타임아웃 확장**: 업로드 10분, 폴링 60분으로 긴 녹음 대응
- **서버 재시작 스크립트**: deploy/restart.sh로 원클릭 재배포

### 22. 동적 회의록 테이블 UI (SPEC-UI-001 ✅)

- **양식 기반 동적 테이블**: 업로드한 PDF/DOCX 양식의 섹션 구조에 맞춰 회의록 테이블 자동 생성
- **섹션별 AI 출력**: AI가 양식 섹션별로 내용을 분리하여 각 테이블 행에 매핑
- **회의 결과 4탭 구조**: 회의 내용 | 회의록 | AI 요약 | 액션 아이템
- **하위 호환성**: 양식 미선택 시 기본 하드코딩 테이블 유지

## 사용 사례

### 일일 스탠드업

매일 오전 9시 30분에 팀 회의를 진행하는 스타트업이 Voice to TextNote를 사용합니다.

1. 한 팀원이 웹 앱에서 "회의 시작" 버튼을 클릭
2. 모든 팀원의 발화가 실시간으로 기록됨
3. 회의 종료 후 자동으로 AI가 요약본과 액션 아이템 생성
4. 회의록이 자동으로 이메일로 배포됨

### 프로젝트 킥오프 미팅

새 프로젝트 시작 시 상세한 회의록이 필요한 경우:

1. 프로젝트 매니저가 회의 녹음 시작
2. 각 부서 대표의 발화가 자동으로 식별되고 기록됨
3. 회의 후 AI가 결정사항, 액션 아이템, 리스크 항목으로 구조화
4. 마크다운 형식의 회의록이 자동으로 프로젝트 위키에 업로드됨

### 분산팀 동기화 미팅

원격 근무 팀의 비동기 미팅 기록:

1. 팀원들이 시간대 차이로 인해 오프라인 비디오 메시지로 의견 제시
2. 각 메시지가 자동으로 음성 텍스트 변환 및 스피커 식별
3. 모든 의견이 통합되어 하나의 회의록으로 정렬
4. 모든 팀원이 통합 회의록과 요약본에 접근 가능

## 프라이버시 이점

### 완전한 로컬 처리

- **제로 클라우드**: 모든 음성 데이터가 조직 내부 M4 Mac Mini에서만 처리
- **데이터 통제**: 외부 서비스(Google, Microsoft, AWS 등)로 데이터 전송 없음
- **규정 준수**: GDPR, CCPA 등 엄격한 개인정보보호 규정 자동 만족

### 암호화

- **전송 암호화**: 클라이언트와 로컬 서버 간 TLS 1.3 암호화
- **저장 암호화**: 선택적 AES-256 암호화로 저장된 회의록 보호
- **엔드-투-엔드**: 클라이언트에서 생성되는 모든 데이터가 암호화

### 감사 및 규정

- **감사 로그**: 회의록 접근 이력 자세히 기록
- **권한 관리**: 팀별 회의록 접근 권한 세밀하게 제어
- **데이터 소유권**: 회의록의 완전한 소유권이 조직에 있음

## 경쟁 우위

| 항목 | Voice to TextNote | Otter.ai | Google Meet 기록 |
|------|------------------|----------|-----------------|
| 로컬 처리 | ✓ | ✗ | ✗ |
| 스피커 식별 | ✓ 자동 | ✓ (유료) | ✗ |
| 프라이버시 | 최고 | 낮음 | 낮음 |
| 초기 비용 | 무료 | 월 $10+ | 무료 |
| 오프라인 지원 | ✓ | ✗ | ✗ |
| 크로스 플랫폼 | ✓ (Flutter) | 제한적 | Google 제품만 |
| AI 요약 | OpenAI gpt-4o-mini | Otter AI | Google Gemini |

## 성공 메트릭

- **채택률**: 첫 3개월 내 50개 팀의 채택
- **일일 회의 기록**: 월 1,000건 이상의 회의 자동 기록
- **사용자 만족도**: NPS 50 이상 달성
- **프라이버시 신뢰도**: 고객 만족도 조사에서 보안/프라이버시 점수 4.5/5 이상
- **비용 절감**: 사용자가 월 평균 5시간 이상의 회의록 작성 시간 절감

## 완료된 마일스톤

### Phase 1 ✅ (완료): MVP 완전 구현

- **SPEC-STT-001**: 기본 녹음 및 STT 기능 (mlx-whisper)
- **SPEC-DIA-001**: 스피커 식별 (pyannote.audio)
- **SPEC-MIN-001**: 회의록 자동 생성
- **SPEC-SUM-001**: OpenAI gpt-4o-mini 요약 및 액션 아이템
- **SPEC-APP-001**: Flutter 클라이언트 (Web + macOS)

### Phase 2 ✅ (완료): 보안 & 인프라

- **SPEC-SEC-001**: API 보안 (인증, 레이트 리미팅, CORS)
- **SPEC-INFRA-001**: 모니터링 (Prometheus, 메트릭)
- **SPEC-ERR-001**: 글로벌 에러 처리
- **SPEC-LOG-001**: 감사 로깅
- **SPEC-DEPLOY-001**: Ubuntu systemd 배포 + Tailscale

### Phase 3 ✅ (완료): 데이터 & 실시간 기능

- **SPEC-DB-001**: PostgreSQL + Alembic
- **SPEC-SSE-001**: SSE 실시간 스트리밍
- **SPEC-PERSIST-001**: 데이터 지속성 통합
- **SPEC-LIFECYCLE-001**: 앱 라이프사이클 관리

### Phase 4 ✅ (완료): 기능 고도화

- **SPEC-HISTORY-001**: 회의 이력 API (페이지네이션, 필터링)
- **SPEC-RETENTION-001**: 데이터 보유 정책 (30일 DB, 24h 임시파일)
- **SPEC-E2E-001**: E2E 통합 테스트 (767개 테스트, 96.94% 커버리지)
- **SPEC-APP-002**: Flutter 기능 강화 (SSE, 오류 UI, Shimmer, 데이터바인딩, Connectivity)

### Phase 5 ✅ (완료): 사용성 & 보안 강화

- **SPEC-EXPORT-001**: 회의록 PDF 내보내기 (fpdf2 + NotoSansKR 한국어)
- **SPEC-ENV-001**: Flutter 환경 설정 분리 (--dart-define 기반 dev/staging/production)
- **SPEC-GUEST-001**: Guest 모드 (24시간 임시 저장, 회원가입 없이 앱 사용)
- **API 인증 활성화**: X-API-Key 헤더 인증 (Flutter + Backend 연동)

### Phase 6 ✅ (완료): 모바일 프로덕션 & 실시간 협업 & 오프라인 STT

- **SPEC-MOBILE-004**: 모바일 프로덕션 완성 (Push 알림, 백그라운드 녹음, 권한 재확인, 녹음 복구)
- **SPEC-COLLAB-001**: 실시간 협업 편집 (WebSocket + LWW + Presence + Flutter 클라이언트)
- **SPEC-MOBILE-002**: 오프라인 STT 하이브리드 파이프라인 (모델 관리 + 로컬 전사 + 재처리 큐)
- **SPEC-MOBILE-005**: iOS 백그라운드 녹음 안정성 고도화 (인터럽션 처리 + 백그라운드 태스크 + 라이프사이클 + 복구)

### Phase 7 ✅ (완료): 보안 강화 & 감정 분석

- **SPEC-SEC-002**: 보안 강화 — 매직 바이트 검증 + iOS ATS/Android Network Security + 보안 헤더 고도화
- **SPEC-SENTIMENT-001**: 텍스트 감정 분석 — OpenAI gpt-4o-mini 기반 화자별/구간별 감정 분석 + emotional_timeline + Flutter 전용 탭

### 23. 실시간 협업 편집 (SPEC-COLLAB-001 ✅)

- **WebSocket 기반 실시간 동기화**: FastAPI WebSocket 엔드포인트로 다중 사용자 실시간 공동 편집
- **LWW (Last-Write-Wins) 충돌 해결**: 클라이언트 타임스탬프 기반으로 일관된 충돌 해결
- **Redis 실시간 상태 캐싱**: 편집 세션, 타임스탬프, Presence 정보를 Redis에 캐싱 (TTL 24시간)
- **Presence 오버레이**: Flutter 클라이언트에서 실시간으로 다른 편집자의 커서 및 활동 표시
- **JWT 쿼리 파라미터 인증**: WebSocket 핸드셰이크에서 `?token=` 기반 JWT 인증

### 24. 오프라인 STT 하이브리드 파이프라인 (SPEC-MOBILE-002 ✅)

- **로컬 STT 모델 관리**: whisper.cpp 모델 다운로드, 검증, 삭제 (SharedPreferences 경로 관리)
- **하이브리드 파이프라인**: 온라인 시 서버 STT 위임, 오프라인 시 로컬 STT → 재처리 큐
- **재처리 큐**: 오프라인 중 로컬 처리된 작업을 연결 복구 시 서버로 재처리 (SharedPreferences 영속화)
- **모델 다운로드 UI**: 상태 기반 UX (notDownloaded → downloading → verifying → ready → error)
- **TranscriptionSource 메타데이터**: 서버/로컬/하이브리드 전사 출처 추적

### 25. 텍스트 감정 분석 (SPEC-SENTIMENT-001 ✅)

- **OpenAI gpt-4o-mini 기반 감정 분석**: 회의록 세그먼트 입력 → 구간별/화자별 감정 분석
- **감정 레이블 체계**: positive/neutral/negative + 세부 감정 (joy/satisfaction/frustration/anger/sadness/surprise)
- **화자별 precomputed 통계**: SpeakerSentiment (positive/neutral/negative 비율, dominant_emotion, emotion_distribution)을 백엔드에서 계산하여 클라이언트에 제공
- **감정 변화 타임라인**: emotional_timeline ({time, sentiment, emotion, speaker}) 시계열 데이터
- **Celery 비동기 처리**: sentiment_celery_task가 minutes_task 완료 후 실행, 동시성 제한 (settings.max_concurrent_sentiment, 기본 3)
- **SSE 실시간 진행률**: task:sentiment:status:{task_id} Redis 키로 진행률 스트리밍
- **Flutter 전용 탭**: _SentimentTab에서 전체 분포, 화자별 통계, 타임라인 시각화, ErrorRetryWidget 제공

### 26. 발화 톤/운율 분석 (Tone Analysis)

음향 특징 기반 발화 톤 분석 기능.

- **엔진**: opensmile eGeMAPSv02 (88차원 음향 특징) + librosa (F0, RMS energy, speaking rate)
- **분류 체계**: 5-class (calm/excited/authoritative/hesitant/monotone) + unknown (confidence < 0.4)
- **처리 파이프라인**: DIA 완료 후 minutes_task와 병렬 실행, 세그먼트별 waveform 슬라이싱 후 prosody 추출
- **오디오 보존**: DIA wav를 tone_task 완료 후까지 보존 (DUAL-PATH: 비활성화 시 기존 즉시 삭제 유지)
- **API**: `/api/v1/tone/{task_id}`, `/api/v1/tone/meeting/{meeting_id}` (tone_model 빈 값 시 503)
- **Flutter**: 감정 분석 탭 내 tone timeline 섹션 (색상 매핑, 에러 격리, 재시도 버튼)
- **메모리 보호**: 19.2GB 초과 시 MemoryError로 분석 중단 (STT/DIA 우선 보호)
- **라이선스**: opensmile AGPL-3.0 (로컬 전용 처리로 회피 가능)

## 다음 단계 (Phase 8 계획)

### 향후 로드맵

- **i18n**: 11개 언어 다국어 지원
- **음성 톤 분석**: 오디오 기반 감정/톤 분석 (텍스트 감정 분석은 Phase 7 완료)
- **클라우드 동기화**: 멀티 기기 지원
- **Slack/Teams 연동**: 외부 협업 도구 통합
