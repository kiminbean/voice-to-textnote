# Interview: 오프라인 STT 처리 (SPEC-MOBILE-002)

## Round 1: Scope

### Question 1: 대상 플랫폼
**Answer**: Android 포함 전 플랫폼 (iOS + macOS + Android)
- iOS: Neural Engine 활용 mlx-whisper 또는 whisper.cpp
- macOS: M4 Mac mini에서 mlx-whisper (기존 백엔드와 동일 엔진)
- Android: whisper.cpp TFLite 런타임

### Question 2: 모델 크기
**Answer**: Base 모델 (균형) — whisper-base (~150MB)
- 속도와 정확도 균형
- 한국어 정확도 ~85%

### Question 3: 온라인 복귀 처리
**Answer**: 오프라인 결과 + 온라인 재처리
- 오프라인 결과 우선 표시
- 네트워크 복구 시 서버 STT (whisper-large-v3)로 재처리 후 결과 교체

## Round 2: Constraints

### Question 4: 모델 다운로드 전략
**Answer**: 최초 실행 시 다운로드 (Wi-Fi)
- 앱 크기 작게 유지
- 다운로드 진행률 UI 필요
- Wi-Fi 감지 시에만 자동 다운로드

### Question 5: 언어 지원
**Answer**: 한국어 우선
- 한국어 전용 최적화로 모델 크기 감소 가능
- 다국어는 향후 확장

## Clarity Score
Initial: 1/10
After Round 1: 6/10
Final: 8/10
Rounds completed: 2
