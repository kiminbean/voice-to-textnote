---
id: SPEC-UX-002
phase: plan
version: "1.0.0"
created: "2026-06-15"
updated: "2026-06-15"
---

# SPEC-UX-002 Implementation Plan

## 개요

SPEC-UX-002는 4개 UX 개선 영역(접근성, 반응형, 국제화, 마이크로 인터랙션)을 구현하여 WCAG 2.1 AA 준수, 태블릿/데스크톱 대응, 다국어 인프라, 체감 품질 향상을 달성한다.

## 개발 방법론

- **TDD (RED-GREEN-REFACTOR)**: 접근성/반응형 테스트 먼저 작성 후 구현
- 각 REQ별로 독립적으로 진행 가능

## 태스크 분해

### Phase 1: P0 (접근성 — 스토어 정책 준수)

#### Task 1: REQ-UX-001 — 핵심 5개 화면 접근성 라벨링

**사전 분석**:
- 13개 화면 중 핵심 5개 선별: home, recording, result, processing, search
- 각 화면의 상호작용 요소(버튼, 아이콘, 리스트, 이미지) 식별

**단계**:
1. 각 화면별로 상호작용 요소 목록 추출 (IconButton, FloatingActionButton, GestureDetector, ListTile 등)
2. 각 요소에 `tooltip` (IconButton/FAB) 또는 `Semantics(label:, hint:)` (복합 위젯) 추가
3. 이미지/아이콘에 의미 있는 설명 제공
4. 포커스 순서 논리적 정렬 (자동: 위젯 트리 순서)

**검증**:
- 각 화면에 대한 widget test에서 `find.byTooltip(...)` 또는 `find.bySemanticsLabel(...)` 통과
- `flutter analyze` clean 유지

### Phase 2: P1 (국제화 — Phase 8 선행 조건)

#### Task 2: REQ-UX-003 — 국제화 인프라 + 핵심 화면 문자열 전환

**사전 분석**:
- `pubspec.yaml`에 `flutter_localizations` 의존성 추가 필요
- `generate: true` 설정 필요

**단계**:
1. `pubspec.yaml` 업데이트:
   ```yaml
   dependencies:
     flutter_localizations:
       sdk: flutter
   flutter:
     generate: true
   ```
2. `l10n.yaml` 생성 (gen-l10n 설정)
3. `lib/l10n/app_ko.arb` 생성 — 한국어 문자열 (기본)
4. `lib/l10n/app_en.arb` 생성 — 영어 번역
5. `MaterialApp`에 `localizationsDelegates` 및 `supportedLocales` 추가
6. 핵심 5개 화면의 주요 문자열을 `AppLocalizations.of(context)!.xxx`로 전환

**검증**:
- `flutter gen-l10n` 실행 성공
- 로케일 변경 테스트에서 문자열 전환 확인

### Phase 3: P2 (반응형 + 마이크로 인터랙션)

#### Task 3: REQ-UX-002 — 홈/결과 화면 반응형 레이아웃

**단계**:
1. `home_screen.dart`:
   - `LayoutBuilder` 추가
   - 600px+에서 `Row` 기반 마스터-디테일 (좌측 리스트, 우측 미리보기)
   - 1200px+에서 더 넓은 디테일 패널
   - 모바일(<600px)은 기존 단일 컬럼 유지
2. `result_screen.dart`:
   - 600px+에서 탭을 `NavigationRail`로 전환
   - 모바일은 기존 `TabBar` 유지

**검증**:
- `tester.view.physicalSize`로 태블릿/데스크톱 해상도 시뮬레이션
- 2컬럼 렌더링 확인

#### Task 4: REQ-UX-004 — 마이크로 인터랙션 5개 지점

**단계**:
1. `recording_screen.dart`:
   - 녹음 버튼: `AnimatedContainer` (색상/크기 전환) + `HapticFeedback.mediumImpact()`
   - 정지 버튼: `HapticFeedback.heavyImpact()`
2. `widgets/meeting_card.dart`:
   - 탭 시 `Hero(tag: 'meeting-$id')` 애니메이션
   - `result_screen.dart`에서 대응하는 `Hero` tag
3. `home_screen.dart`:
   - `RefreshIndicator` + 새로고침 완료 시 `AnimatedSwitcher`
4. `widgets/error_retry_widget.dart`:
   - `AnimatedOpacity`로 에러 페이드인/아웃
5. `processing_screen.dart`:
   - 완료 시 `HapticFeedback.heavyImpact()` + 체크 아이콘 `AnimationController`

**검증**:
- 각 파일에 애니메이션/haptic 코드 포함
- widget test에서 애니메이션 위젯 존재 확인

## 병렬 실행 가능성

| Task Group | 병렬 가능 | 이유 |
|-----------|----------|------|
| Task 1 + Task 2 | ✓ | 독립 파일 (접근성 vs l10n 인프라) |
| Task 3 + Task 4 | ✓ | 홈/결과 반응형 vs 녹음/카드 인터랙션 |
| Task 1 → Task 3 | 순차 | 반응형이 접근성 라벨을 포함해야 함 |

## 파일 변경 예상 목록

### 수정 (예상)
- `pubspec.yaml` — flutter_localizations, generate: true
- `lib/main.dart` — localizationsDelegates, supportedLocales
- `lib/screens/home_screen.dart` — 접근성 + 반응형 + i18n
- `lib/screens/recording_screen.dart` — 접근성 + 햅틱
- `lib/screens/result_screen.dart` — 접근성 + 반응형 + Hero
- `lib/screens/processing_screen.dart` — 접근성 + 완료 애니메이션
- `lib/screens/search_screen.dart` — 접근성 + i18n
- `lib/widgets/meeting_card.dart` — Hero 애니메이션
- `lib/widgets/error_retry_widget.dart` — AnimatedOpacity

### 신규 (예상)
- `l10n.yaml` — gen-l10n 설정
- `lib/l10n/app_ko.arb` — 한국어 문자열
- `lib/l10n/app_en.arb` — 영어 번역
- `lib/l10n/app_localizations.dart` — gen-l10n 생성 (자동)
- 접근성/반응형 widget 테스트 파일 3-5개

## 리스크 완화

| 리스크 | 완화책 |
|--------|--------|
| i18n 전환 누락 | 점진적 전환, ARB 키 커버리지 테스트 |
| 반응형 모바일 회귀 | LayoutBuilder fallback (기존 모바일 레이아웃 유지) |
| 애니메이션 성능 | `const` 위젯, `RepaintBoundary` 사용 |

## 완료 기준

- [ ] AC-001~005 전부 통과
- [ ] `flutter analyze`: No issues found!
- [ ] `flutter test`: 328+ passed
- [ ] 핵심 5개 화면의 상호작용 요소 100% 접근성 라벨 포함
- [ ] `flutter gen-l10n` 성공
- [ ] home_screen 600px+에서 마스터-디테일 렌더링
- [ ] 5개 마이크로 인터랙션 지점에 애니메이션/haptic 포함
