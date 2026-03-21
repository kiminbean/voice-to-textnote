---
id: SPEC-DOCKER-001
version: "1.0.0"
status: completed
created: 2026-03-21
updated: 2026-03-21
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-DOCKER-001: Docker 프로덕션 구성 - Nginx, PostgreSQL, 환경 분리

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-21 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 컨테이너 | Docker, Docker Compose |
| 리버스 프록시 | Nginx alpine |
| 데이터베이스 | PostgreSQL 16 alpine |
| 기존 서비스 | Redis 7, FastAPI, Celery Worker |

---

## 2. 가정 (Assumptions)

- 기존 docker-compose.yml은 개발용으로 유지하고, docker-compose.prod.yml을 별도 생성한다.
- PostgreSQL은 인프라로만 추가하며, 앱 코드에서의 DB 연동은 별도 SPEC으로 분리한다.
- Nginx는 리버스 프록시 + 정적 파일 서빙 + /metrics 접근 제한을 담당한다.
- SSL/TLS 인증서는 자체 서명 또는 Let's Encrypt 지원 구조를 제공한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: 프로덕션 Docker Compose

**[REQ-DOCKER-001] [유비쿼터스]** docker-compose.prod.yml은 최소 5개 서비스(nginx, api, worker, redis, postgres)를 정의해야 한다.

**[REQ-DOCKER-002] [유비쿼터스]** 모든 서비스는 healthcheck를 포함하고 의존성 순서가 정의되어야 한다.

**[REQ-DOCKER-003] [유비쿼터스]** PostgreSQL 데이터는 명명된 볼륨(postgres_data)에 영속 저장해야 한다.

### 모듈 2: Nginx 리버스 프록시

**[REQ-DOCKER-004] [유비쿼터스]** Nginx는 80/443 포트로 외부 요청을 받아 FastAPI(8000)로 프록시해야 한다.

**[REQ-DOCKER-005] [유비쿼터스]** /metrics 엔드포인트는 내부 네트워크에서만 접근 가능하도록 제한해야 한다.

**[REQ-DOCKER-006] [유비쿼터스]** Nginx는 gzip 압축, 요청 크기 제한(500MB), 프록시 타임아웃(300s)을 설정해야 한다.

**[REQ-DOCKER-007] [유비쿼터스]** SSL/TLS 구성을 위한 인증서 마운트 구조를 제공해야 한다.

### 모듈 3: 환경 변수 완성

**[REQ-DOCKER-008] [유비쿼터스]** .env.example은 모든 서비스의 환경 변수를 섹션별로 문서화해야 한다.

**[REQ-DOCKER-009] [유비쿼터스]** .env.production.example은 프로덕션 권장 값을 포함해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: 프로덕션 Compose 유효성
- **Given** docker-compose.prod.yml 존재
- **When** docker compose -f docker-compose.prod.yml config 실행
- **Then** 유효한 설정으로 파싱 성공

### AC-2: Nginx 프록시 설정
- **Given** nginx/nginx.conf 존재
- **When** nginx -t 실행
- **Then** 설정 검증 통과

### AC-3: /metrics 접근 제한
- **Given** Nginx 설정에 /metrics 제한
- **When** 외부에서 /metrics 접근
- **Then** 403 Forbidden

### AC-4: 환경 변수 완성
- **Given** .env.example 확인
- **When** 모든 Settings 필드와 비교
- **Then** 누락된 변수 없음

---

## 5. 기술 접근 방식

### 파일 구조

```
project-root/
├── docker-compose.prod.yml       # 프로덕션 Compose
├── nginx/
│   ├── nginx.conf                # Nginx 메인 설정
│   └── ssl/                      # SSL 인증서 디렉토리 (빈 폴더)
├── .env.example                  # 개발용 환경 변수 (업데이트)
├── .env.production.example       # 프로덕션용 환경 변수
```
