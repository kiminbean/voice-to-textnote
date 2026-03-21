---
id: SPEC-APP-002
version: "1.0.0"
status: completed
created: 2026-03-21
updated: 2026-03-21
author: kisoo
priority: P1
issue_number: 0
---

# SPEC-APP-002: Flutter 클라이언트 고도화 - 에러 UI, SSE 연동, 로딩 상태

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-21 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 프레임워크 | Flutter 3.24+, Dart 3.5+ |
| 상태관리 | flutter_riverpod 2.6.1 |
| HTTP | dio 5.9.2 |
| 라우팅 | go_router 15.1.2 |
| SSE | http 패키지 (dart:io StreamedResponse) |
| 로딩 | shimmer 3.0.0+ |
| 연결 감지 | connectivity_plus 6.0.0+ |
| 테스트 | flutter_test, mocktail 1.0.4 |

---

## 2. 가정 (Assumptions)

- 백엔드 SSE 엔드포인트(GET /api/v1/tasks/{task_id}/stream)가 정상 동작한다 (SPEC-SSE-001 완료).
- 기존 폴링 방식은 SSE 폴백으로 유지한다 (SSE 연결 실패 시).
- 에러 UI는 Material 3 디자인 시스템을 따른다.
- 로딩 상태는 shimmer 패키지를 사용한다.
- 현재 37개 테스트는 모두 유지되어야 한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: SSE 실시간 스트리밍 서비스 (폴링 대체)

**[REQ-APP2-001] [이벤트 기반]** WHEN ProcessingScreen이 열릴 때 THEN SSE 스트림(/api/v1/tasks/{task_id}/stream)에 연결하여 실시간 상태 업데이트를 수신해야 한다.

**[REQ-APP2-002] [이벤트 기반]** WHEN SSE 이벤트 수신 THEN PipelineState를 즉시 업데이트하여 UI에 반영해야 한다.

**[REQ-APP2-003] [이벤트 기반]** WHEN SSE 연결 실패 또는 끊김 THEN 기존 폴링 방식으로 자동 폴백해야 한다.

**[REQ-APP2-004] [이벤트 기반]** WHEN ProcessingScreen이 닫힐 때 THEN SSE 스트림 구독을 해제하고 리소스를 정리해야 한다.

**[REQ-APP2-005] [이벤트 기반]** WHEN completed 또는 failed 이벤트 수신 THEN 자동으로 결과 화면으로 이동하거나 에러 UI를 표시해야 한다.

### 모듈 2: 에러 UI 컴포넌트

**[REQ-APP2-006] [이벤트 기반]** WHEN API 호출 실패 THEN ErrorDialog를 표시하고 "재시도" 및 "홈으로" 옵션을 제공해야 한다.

**[REQ-APP2-007] [유비쿼터스]** 시스템은 네트워크 연결 상태를 모니터링하고 오프라인 시 상단에 배너를 표시해야 한다.

**[REQ-APP2-008] [이벤트 기반]** WHEN 파이프라인 처리 실패 THEN 실패 단계와 에러 메시지를 포함한 상세 에러 화면을 표시해야 한다.

**[REQ-APP2-009] [유비쿼터스]** 모든 에러 메시지는 사용자 친화적 한국어로 표시되어야 한다 (기술적 에러 코드 미노출).

### 모듈 3: 로딩 상태 (Shimmer/Skeleton)

**[REQ-APP2-010] [유비쿼터스]** HomeScreen 미팅 목록 로딩 시 shimmer 카드 플레이스홀더를 표시해야 한다.

**[REQ-APP2-011] [유비쿼터스]** ResultScreen 데이터 로딩 시 텍스트/카드 스켈레톤을 표시해야 한다.

**[REQ-APP2-012] [유비쿼터스]** ProcessingScreen 진행 중 시각적 펄스 애니메이션을 적용해야 한다.

### 모듈 4: ResultScreen 실제 데이터 연동

**[REQ-APP2-013] [이벤트 기반]** WHEN ResultScreen 진입 THEN API에서 실제 회의록/요약/액션 아이템 데이터를 로드해야 한다.

**[REQ-APP2-014] [이벤트 기반]** WHEN 데이터 로드 실패 THEN "데이터를 불러올 수 없습니다" 에러 위젯과 재시도 버튼을 표시해야 한다.

**[REQ-APP2-015] [이벤트 기반]** WHEN 데이터가 비어있을 때 THEN "아직 처리된 결과가 없습니다" 빈 상태 위젯을 표시해야 한다.

### 모듈 5: 연결 상태 관리

**[REQ-APP2-016] [유비쿼터스]** 앱은 /api/v1/health를 주기적(30초)으로 호출하여 서버 연결 상태를 확인해야 한다.

**[REQ-APP2-017] [이벤트 기반]** WHEN 서버 연결 끊김 감지 THEN "새 녹음" 버튼을 비활성화하고 오프라인 안내를 표시해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: SSE 스트림 연결
- **Given** ProcessingScreen 진입
- **When** task_id로 SSE 연결
- **Then** 서버 이벤트를 실시간으로 수신하여 UI에 반영

### AC-2: SSE 폴백
- **Given** SSE 연결 실패
- **When** 폴백 활성화
- **Then** 기존 폴링(2초)으로 자동 전환 + "실시간 연결 불가" 토스트

### AC-3: 에러 다이얼로그
- **Given** API 호출 실패 (예: 500 에러)
- **When** 에러 발생
- **Then** "처리 중 오류가 발생했습니다" 다이얼로그 + 재시도/홈 버튼

### AC-4: 오프라인 배너
- **Given** 서버 연결 불가
- **When** 헬스체크 실패
- **Then** 화면 상단에 "서버에 연결할 수 없습니다" 배너

### AC-5: 로딩 shimmer
- **Given** HomeScreen 진입
- **When** 데이터 로딩 중
- **Then** shimmer 카드 플레이스홀더 3개 표시

### AC-6: 결과 실제 데이터
- **Given** ResultScreen 진입 (meeting_id)
- **When** API 데이터 로드 성공
- **Then** 하드코딩 대신 실제 회의록/요약/액션 아이템 표시

### AC-7: 결과 에러 상태
- **Given** ResultScreen API 호출 실패
- **When** 에러 발생
- **Then** 에러 위젯 + "다시 시도" 버튼

---

## 5. 기술 접근 방식

### 파일 구조

```
client/lib/
├── services/
│   ├── sse_service.dart          # SSE 스트림 서비스 (신규)
│   └── connectivity_service.dart # 연결 상태 서비스 (신규)
├── providers/
│   ├── pipeline_provider.dart    # SSE 통합 (수정)
│   ├── connectivity_provider.dart # 연결 상태 Provider (신규)
│   └── result_provider.dart      # 결과 데이터 Provider (신규)
├── widgets/
│   ├── error_dialog.dart         # 에러 다이얼로그 (신규)
│   ├── offline_banner.dart       # 오프라인 배너 (신규)
│   ├── shimmer_card.dart         # shimmer 카드 (신규)
│   ├── shimmer_text.dart         # shimmer 텍스트 (신규)
│   ├── error_retry_widget.dart   # 에러+재시도 위젯 (신규)
│   └── empty_state_widget.dart   # 빈 상태 위젯 (신규)
├── screens/
│   ├── home_screen.dart          # shimmer + 오프라인 (수정)
│   ├── processing_screen.dart    # SSE 통합 + 에러 UI (수정)
│   └── result_screen.dart        # 실제 데이터 + 에러/빈 상태 (수정)
```

### 의존성 추가 (pubspec.yaml)

```yaml
dependencies:
  shimmer: ^3.0.0
  connectivity_plus: ^6.0.0
```

### SSE 구현 전략

Dart의 `http` 패키지 `Client.send()`로 SSE 스트림을 수신합니다:
```dart
final request = Request('GET', Uri.parse('$baseUrl/api/v1/tasks/$taskId/stream'));
final response = await client.send(request);
await for (final chunk in response.stream.transform(utf8.decoder).transform(LineSplitter())) {
  // SSE 이벤트 파싱 (data: {...})
}
```

폴백: SSE 연결 3초 내 실패 시 기존 Timer.periodic 폴링으로 전환.
