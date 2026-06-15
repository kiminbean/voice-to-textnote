---
id: SPEC-UX-002
version: "1.0.0"
status: planned
created: "2026-06-15"
updated: "2026-06-15"
author: MoAI
priority: high
issue_number: 0
---

# SPEC-UX-002: 사용자 경험 개선 — 접근성, 반응형 디자인, 국제화 기반, 마이크로 인터랙션

## HISTORY

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-06-15 | 1.0.0 | Initial SPEC — 4개 UX 개선 영역 정의 | MoAI |

## 개요

Voice to TextNote의 Flutter 클라이언트는 기능적으로 완성되었으나, 사용자 경험 측면에서 4가지 주요 갭이 존재한다:

1. **접근성 (WCAG 2.1 AA)**: 35개 위젯/화면 중 단 2개만 `Semantics`/`semanticLabel` 사용 — 스크린 리더 사용자가 앱을 사실상 사용 불가
2. **반응형 디자인**: 35개 파일 중 1개만 `MediaQuery`/`LayoutBuilder` 사용 — 태블릿/데스크톱에서 레이아웃 최적화 없음
3. **국제화 (i18n)**: 모든 UI 문자열이 한국어로 하드코딩 — Phase 8 다국어 지원의 선행 조건 미충족
4. **마이크로 인터랙션**: 35개 파일 중 3개만 애니메이션 위젯 사용 — 화면 전환, 로딩, 피드백이 정적

본 SPEC은 이러한 UX 갭을 해소하여:
- WCAG 2.1 AA 준수 (App Store/Google Play 접근성 요구사항 충족)
- 태블릿/데스크톱 레이아웃 최적화
- 다국어 지원 인프라 구축 (Phase 8 준비)
- 체감 품질 향상 (애니메이션, 햅틱 피드백)

## 요구사항 (EARS Format)

### REQ-UX-001: 핵심 화면 접근성 라벨링

- **When** 스크린 리더(TalkBack/VoiceOver)가 활성화된 상태에서 사용자가 앱을 탐색할 때
- **Then** 모든 상호작용 가능 요소(버튼, 아이콘, 이미지, 리스트 아이템)가 의미 있는 접근성 라벨을 가져야 한다
- **Rationale**: 현재 2/35 파일만 Semantics 사용. App Store/Google Play 접근성 정책 충족 필요.

**대상 화면** (우선순위 순):
1. `home_screen.dart` — 회의 목록, 팝업 메뉴, FAB
2. `recording_screen.dart` — 녹음 버튼, 타이머, 파형
3. `result_screen.dart` — 탭 전환, 회의록, 요약, 액션 아이템
4. `processing_screen.dart` — 진행률 표시
5. `search_screen.dart` — 검색바, 필터, 결과

**검증 방법**:
- 각 화면의 상호작용 요소에 `Semantics(label: ..., hint: ...)` 또는 `Tooltip(message: ...)` 추가
- 아이콘 전용 버튼(`IconButton`, `FloatingActionButton`)은 필수적으로 `tooltip` 속성 포함
- `flutter test`에서 접근성 위젯 테스트 통과

### REQ-UX-002: 반응형 레이아웃 (태블릿/데스크톱)

- **When** 화면 너비가 600px 이상(태블릿) 또는 1200px 이상(데스크톱)일 때
- **Then** 홈 화면과 결과 화면이 2컬럼 마스터-디테일 레이아웃으로 전환되어야 한다
- **Rationale**: 현재 모든 화면이 단일 컬럼 모바일 레이아웃. iPad/데스크톱에서 공간 낭비.

**대상**:
1. `home_screen.dart` — 마스터-디테일: 좌측 회의 목록, 우측 선택된 회의 미리보기
2. `result_screen.dart` — 넓은 화면에서 탭을 Side Navigation으로 전환
3. `search_screen.dart` — 결과를 그리드/리스트 전환 가능

**검증 방법**:
- `LayoutBuilder` 또는 `MediaQuery.sizeOf` 기반 브레이크포인트 (600px, 1200px)
- `flutter test`에서 `tester.binding.window.physicalSizeTestValue`로 태블릿 해상도 시뮬레이션
- 위젯이 2컬럼으로 렌더링되는지 확인

### REQ-UX-003: 국제화 인프라 구축

- **When** 앱이 실행될 때
- **Then** 시스템 로케일에 따라 UI 문자열이 번역되어야 한다 (기본: 한국어)
- **Rationale**: 모든 문자열이 하드코딩. Phase 8 i18n의 선행 조건.

**단계**:
1. `flutter gen-l10n` 기반 ARB 파일 구조 생성 (`lib/l10n/app_ko.arb`, `app_en.arb`)
2. `pubspec.yaml`에 `generate: true` 및 `flutter_localizations` 의존성 추가
3. 핵심 화면 5개의 하드코딩 문자열을 `AppLocalizations` 참조로 전환
4. 한국어(`ko`)와 영어(`en`) 기본 번역 제공

**검증 방법**:
- `flutter gen-l10n` 실행 시 오류 없이 생성
- `AppLocalizations.of(context)!.xxx` 형태로 문자열 참조
- `flutter test`에서 로케일 변경 시 문자열 전환 확인
- `grep -rn "'[가-힣]" client/lib/screens/` 감소 (문자열 추출 진행도)

### REQ-UX-004: 마이크로 인터랙션 및 햅틱 피드백

- **When** 사용자가 버튼을 탭하거나, 항목을 스와이프하거나, 작업이 완료될 때
- **Then** 시각적 애니메이션과 햅틱 피드백이 제공되어야 한다
- **Rationale**: 현재 3/35 파일만 애니메이션 사용. 피드백 부재로 조작 확인감 저하.

**대상**:
1. 녹음 시작/중지 버튼 — `AnimatedContainer`로 크기/색상 전환, `HapticFeedback.mediumImpact()`
2. 회의 카드 탭 — `Hero` 애니메이션으로 결과 화면으로 전환
3. 새로고침 완료 — `AnimatedSwitcher`로 로딩→데이터 전환
4. 에러 발생 — `AnimatedOpacity`로 에러 위젯 페이드인
5. 다운로드/처리 완료 — `HapticFeedback.heavyImpact()` + 체크 애니메이션

**검증 방법**:
- 각 인터랙션에 애니메이션/haptic 코드 포함
- `flutter test`에서 애니메이션 위젯 존재 확인
- 햅틱은 `HapticFeedback` import 및 호출로 검증

## 인수 기준 (Acceptance Criteria)

### AC-001: 접근성 라벨링
- 핵심 5개 화면의 모든 상호작용 요소에 Semantics/Tooltip 추가
- `flutter test`에서 `find.byType(Semantics)` 카운트가 기준치 이상
- 아이콘 전용 버튼 100% tooltip 포함

### AC-002: 반응형 레이아웃
- `home_screen.dart`가 600px+에서 마스터-디테일 렌더링
- `LayoutBuilder` 사용한 브레이크포인트 로직 포함
- 태블릿 해상도 테스트 통과

### AC-003: 국제화 인프라
- `lib/l10n/app_ko.arb` + `app_en.arb` 생성
- `pubspec.yaml` localization 설정 추가
- 핵심 5개 화면의 주요 문자열 `AppLocalizations` 참조로 전환
- `flutter gen-l10n` 성공

### AC-004: 마이크로 인터랙션
- 녹화 버튼, 회의 카드, 새로고침, 에러, 완료 5개 지점에 애니메이션/haptic 추가
- `flutter test`에서 애니메이션 위젯/`HapticFeedback` 호출 검증

### AC-005: 전체 게이트 유지
- `flutter analyze`: No issues found!
- `flutter test`: 328+ passed (기존 + 신규 접근성/반응형 테스트)
- 다운로드 크기 영향 5% 미만 (l10n ARB 파일 가벼움)

## 기술 접근법

### 접근성 패턴

```dart
// 아이콘 버튼
IconButton(
  icon: const Icon(Icons.search),
  tooltip: '검색', // 접근성 라벨
  onPressed: () => context.push('/search'),
)

// 복합 위젯
Semantics(
  label: '회의 녹음본',
  hint: '탭하여 상세 내용을 확인하세요',
  button: true,
  child: MeetingCard(meeting: meeting),
)
```

### 반응형 레이아웃 패턴

```dart
LayoutBuilder(
  builder: (context, constraints) {
    if (constraints.maxWidth >= 1200) {
      return _DesktopLayout(meetings: meetings);
    } else if (constraints.maxWidth >= 600) {
      return _TabletLayout(meetings: meetings);
    }
    return _MobileLayout(meetings: meetings);
  },
)
```

### 국제화 패턴

```dart
// l10n/app_ko.arb
{
  "@@locale": "ko",
  "appTitle": "Voice to TextNote",
  "recordButton": "녹음 시작"
}

// 사용
Text(AppLocalizations.of(context)!.appTitle)
```

### 마이크로 인터랙션 패턴

```dart
// 햅틱 + 애니메이션
await HapticFeedback.mediumImpact();
AnimatedContainer(
  duration: const Duration(milliseconds: 200),
  curve: Curves.easeInOut,
  // ...
)
```

## 영향 범위

### 수정 대상 파일 (예상)

**접근성** (5개 화면):
- `home_screen.dart`, `recording_screen.dart`, `result_screen.dart`, `processing_screen.dart`, `search_screen.dart`

**반응형** (2개 화면):
- `home_screen.dart`, `result_screen.dart`

**국제화** (신규 + 수정):
- `lib/l10n/app_ko.arb` (신규), `lib/l10n/app_en.arb` (신규)
- `pubspec.yaml` (localization 설정)
- 5개 화면 문자열 전환

**마이크로 인터랙션** (3-5개 파일):
- `recording_screen.dart`, `widgets/meeting_card.dart`, `processing_screen.dart`, `widgets/error_retry_widget.dart`

### 의존성 추가
- `flutter_localizations` (SDK)
- 기존 의존성 변경 없음

## 우선순위

| REQ | 우선순위 | 이유 |
|-----|---------|------|
| REQ-UX-001 (접근성) | P0 | App Store/Google Store 정책 준수, 사용자 기본권 |
| REQ-UX-003 (i18n) | P1 | Phase 8 선행 조건, 구조적 변경 |
| REQ-UX-002 (반응형) | P2 | 태블릿 사용성, 마켓 확장 |
| REQ-UX-004 (마이크로 인터랙션) | P2 | 체감 품질 향상 |

## 리스크

| 리스크 | 확률 | 영향 | 완화책 |
|--------|------|------|--------|
| i18n 전환 시 문자열 누락 | 중간 | 일부 UI 영어로 표시 | 점진적 전환, ARB 키 커버리지 테스트 |
| 반응형 레이아웃 모바일 회귀 | 낮음 | 기존 모바일 UI 깨짐 | LayoutBuilder fallback 유지 |
| 접근성 라벨 품질 | 중간 | 스크린 리더 경험 저하 | 실제 VoiceOver/TalkBack 테스트 권장 |
| 다운로드 크기 증가 | 낮음 | ARB 파일 추가 | 2개 언어만 초기 추가, 크기 미미 |
