# SPEC-ENV-001 진행 상황

## 현재 상태: COMPLETED

## 2026-03-29

### 초기 분석 완료
- 현재 `AppConfig.apiBaseUrl`이 3곳에서 사용됨 (api_client, auth_api, processing_screen)
- 모두 런타임 값 할당이므로 getter 변환 안전함
- 기존 테스트에서 AppConfig 직접 참조 없음 확인

### TDD 사이클 완료

**RED**
- `client/test/config/app_config_test.dart` 작성 (4개 테스트 케이스)
- `Environment` enum 미정의로 컴파일 실패 확인

**GREEN**
- `client/lib/config/app_config.dart` 수정
  - `Environment` enum 추가 (dev, staging, production)
  - `apiBaseUrl` → getter로 변환 (환경별 분기)
  - `isDebugMode` getter 추가
- 4개 명세 테스트 + 기존 177개 테스트 전부 통과

**REFACTOR**
- `flutter analyze` 경고 없음 확인
- 런치 스크립트 3개 생성 (run_dev.sh, run_staging.sh, run_production.sh)
- @MX:ANCHOR 태그 추가 (fan_in >= 3)
