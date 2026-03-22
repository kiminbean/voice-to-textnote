# SPEC-TEAM-001: 팀 협업 및 권한 관리 - 인수 테스트

## 시나리오 1: 사용자 등록 및 로그인

```gherkin
Given 시스템에 등록되지 않은 이메일 "alice@example.com"이 존재할 때
When 사용자가 POST /api/v1/auth/register에 다음 정보를 전송하면
  | email              | password   | display_name |
  | alice@example.com  | Pass1234   | Alice Kim    |
Then 시스템은 201 상태 코드를 반환하고
And 응답에 access_token과 refresh_token이 포함되어 있고
And access_token을 디코딩하면 user_id와 email이 포함되어 있고
And DB의 users 테이블에 해당 사용자가 생성되어 있다
```

```gherkin
Given 등록된 사용자 "alice@example.com" (비밀번호: "Pass1234")이 존재할 때
When 사용자가 POST /api/v1/auth/login에 올바른 자격 증명을 전송하면
Then 시스템은 200 상태 코드를 반환하고
And 응답에 access_token과 refresh_token이 포함되어 있다
```

```gherkin
Given 유효하지 않은 비밀번호 "wrong"으로 로그인을 시도할 때
When 사용자가 POST /api/v1/auth/login에 잘못된 자격 증명을 전송하면
Then 시스템은 401 상태 코드를 반환하고
And "이메일 또는 비밀번호가 올바르지 않습니다" 오류 메시지를 반환한다
```

---

## 시나리오 2: 토큰 갱신 및 로그아웃

```gherkin
Given 유효한 refresh_token을 가진 사용자가 존재할 때
When POST /api/v1/auth/refresh에 refresh_token을 전송하면
Then 시스템은 200 상태 코드를 반환하고
And 새로운 access_token과 refresh_token을 발급하고
And 기존 refresh_token은 무효화된다 (재사용 불가)
```

```gherkin
Given 로그인한 사용자가 존재할 때
When POST /api/v1/auth/logout에 refresh_token을 전송하면
Then 시스템은 200 상태 코드를 반환하고
And 해당 refresh_token은 즉시 무효화되고
And 무효화된 refresh_token으로 갱신 시도 시 401을 반환한다
```

---

## 시나리오 3: 팀 생성 및 관리

```gherkin
Given 인증된 사용자 Alice가 존재할 때
When Alice가 POST /api/v1/teams에 다음 정보를 전송하면
  | name          | description            |
  | 개발팀        | 백엔드 개발 팀          |
Then 시스템은 201 상태 코드를 반환하고
And 응답에 team_id, name, description이 포함되어 있고
And Alice는 해당 팀의 admin 역할로 자동 등록되어 있고
And GET /api/v1/teams 응답에 "개발팀"이 포함되어 있다
```

```gherkin
Given "개발팀"의 admin인 Alice가 존재할 때
When Alice가 PUT /api/v1/teams/{team_id}에 이름을 "프론트엔드팀"으로 변경하면
Then 시스템은 200 상태 코드를 반환하고
And 팀 이름이 "프론트엔드팀"으로 변경된다
```

```gherkin
Given "개발팀"의 member인 Bob이 존재할 때
When Bob이 PUT /api/v1/teams/{team_id}에 이름 변경을 시도하면
Then 시스템은 403 상태 코드를 반환하고
And "admin 권한이 필요합니다" 오류 메시지를 반환한다
```

---

## 시나리오 4: 팀 멤버 초대 및 역할 관리

```gherkin
Given "개발팀"의 admin인 Alice와 등록된 사용자 Bob이 존재할 때
When Alice가 POST /api/v1/teams/{team_id}/members에 다음 정보를 전송하면
  | email             | role   |
  | bob@example.com   | member |
Then 시스템은 201 상태 코드를 반환하고
And Bob이 "개발팀"의 member 역할로 등록되고
And GET /api/v1/teams/{team_id}/members에 Bob이 포함되어 있다
```

```gherkin
Given "개발팀"의 admin인 Alice와 member인 Bob이 존재할 때
When Alice가 PUT /api/v1/teams/{team_id}/members/{bob_id}에 역할을 "viewer"로 변경하면
Then 시스템은 200 상태 코드를 반환하고
And Bob의 역할이 "viewer"로 변경된다
```

```gherkin
Given "개발팀"의 유일한 admin인 Alice가 존재할 때
When Alice가 DELETE /api/v1/teams/{team_id}/members/{alice_id}로 자신을 제거하려 하면
Then 시스템은 400 상태 코드를 반환하고
And "팀에는 최소 1명의 admin이 필요합니다" 오류 메시지를 반환한다
```

```gherkin
Given "개발팀"의 admin인 Alice가 미가입 이메일을 초대하려 할 때
When Alice가 POST /api/v1/teams/{team_id}/members에 미가입 이메일을 전송하면
Then 시스템은 404 상태 코드를 반환하고
And "해당 이메일로 등록된 사용자가 없습니다" 오류 메시지를 반환한다
```

---

## 시나리오 5: 회의록 팀 공유

```gherkin
Given "개발팀"의 member인 Alice가 자신의 회의록 task-123을 소유하고 있을 때
When Alice가 POST /api/v1/meetings/task-123/share에 team_id를 전송하면
Then 시스템은 200 상태 코드를 반환하고
And meeting_ownership 테이블에 팀 공유 기록이 생성되고
And "개발팀"의 모든 멤버가 해당 회의록을 조회할 수 있다
```

```gherkin
Given "개발팀"에 공유된 회의록 task-123이 존재하고 팀 멤버 Bob이 있을 때
When Bob이 GET /api/v1/teams/{team_id}/meetings를 요청하면
Then 응답에 task-123 회의록이 포함되어 있다
```

```gherkin
Given "개발팀"의 viewer인 Charlie가 자신의 회의록을 소유하고 있지 않을 때
When Charlie가 POST /api/v1/meetings/task-456/share를 시도하면
Then 시스템은 403 상태 코드를 반환한다
```

---

## 시나리오 6: Flutter 로그인 플로우

```gherkin
Given 앱이 처음 실행되었고 저장된 토큰이 없을 때
When 사용자가 앱을 열면
Then 로그인 화면이 표시되고
And 이메일과 비밀번호 입력 필드가 표시된다
```

```gherkin
Given 로그인 화면에서 유효한 자격 증명을 입력했을 때
When "로그인" 버튼을 탭하면
Then Access Token과 Refresh Token이 SecureStorage에 저장되고
And 메인 화면(홈)으로 자동 이동한다
```

```gherkin
Given 저장된 Access Token이 만료되었고 유효한 Refresh Token이 존재할 때
When API 요청이 401을 반환하면
Then Dio 인터셉터가 자동으로 /auth/refresh를 호출하고
And 새 토큰을 저장하고
And 원래 요청을 재시도한다
```

---

## 시나리오 7: Flutter 팀 관리 플로우

```gherkin
Given 로그인한 사용자가 팀 목록 화면에 진입했을 때
When 사용자가 속한 팀이 2개 존재하면
Then 2개의 팀 카드가 표시되고
And 각 카드에 팀 이름, 멤버 수, 사용자의 역할이 표시된다
```

```gherkin
Given 팀 상세 화면에서 admin 역할의 사용자가 있을 때
When "멤버 초대" 버튼을 탭하면
Then 이메일 입력 다이얼로그가 표시되고
And 역할 선택(member/viewer) 드롭다운이 표시되고
And "초대" 버튼을 탭하면 API를 호출하여 멤버를 추가한다
```

---

## 시나리오 8: 하위 호환성

```gherkin
Given 기존 API Key "test-key-123"이 설정되어 있을 때
When X-API-Key 헤더에 "test-key-123"을 포함하여 GET /api/v1/health를 요청하면
Then 시스템은 200 상태 코드를 반환하고
And 기존 API Key 인증이 정상 동작한다
```

```gherkin
Given JWT Access Token을 가진 사용자가 존재할 때
When Authorization: Bearer {token} 헤더로 기존 API(transcription, history 등)를 요청하면
Then 시스템은 정상 응답을 반환하고
And 요청이 JWT 인증으로 처리된다
```

---

## Quality Gates

### 백엔드

| 항목 | 기준 |
|------|------|
| 테스트 커버리지 | 85% 이상 (새 코드) |
| 단위 테스트 | 모든 API 엔드포인트 + 비즈니스 로직 |
| 통합 테스트 | 전체 플로우 (등록 -> 로그인 -> 팀 -> 공유) |
| 보안 테스트 | JWT 만료, Token Rotation, 권한 에스컬레이션 |
| ruff/black | 린트/포맷 에러 0개 |
| mypy | 타입 에러 0개 |
| Alembic | 마이그레이션 정방향/역방향 모두 성공 |

### Flutter

| 항목 | 기준 |
|------|------|
| 위젯 테스트 | 로그인, 회원가입, 팀 목록, 팀 상세 화면 |
| 단위 테스트 | AuthService, TeamService, Provider |
| dart analyze | 경고 0개 |
| 인증 플로우 | 로그인 -> 자동 갱신 -> 로그아웃 검증 |

### 보안

| 항목 | 기준 |
|------|------|
| 비밀번호 | bcrypt cost 12, 평문 저장/로깅 금지 |
| JWT | HS256, 15분 만료, Secret 32자 이상 |
| Refresh Token | DB 해시 저장, 7일 만료, Rotation |
| 권한 | admin/member/viewer 분리 검증 |
| SQL Injection | SQLAlchemy ORM 사용 (raw SQL 금지) |
| Rate Limiting | 로그인 실패 5회 -> 5분 잠금 |
