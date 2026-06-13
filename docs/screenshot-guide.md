# 스크린샷 가이드 (T-017)

**SPEC-MOBILE-004 | 작성일: 2026-06-13**

---

## 필수 스크린샷 사이즈

### iOS (App Store)

| 기기 | 해상도 | 필수 |
|------|--------|------|
| iPhone 6.7" | 1290 x 2796 | 필수 |
| iPhone 6.5" | 1242 x 2688 | 필수 (6.7"로 대체 가능) |
| iPad 12.9" | 2048 x 2732 | iPad 지원 시 필수 |

### Android (Google Play)

| 기기 | 해상수 | 필수 |
|------|--------|------|
| Phone | 1080 x 1920 이상 | 필수 (최소 2장, 최대 8장) |
| Tablet | 1200 x 1920 이상 | 권장 |

---

## 스크린샷 시나리오 (최소 5장)

1. **홈 화면**: 회의록 목록 — 직관적인 히스토리 관리
2. **녹음 화면**: 큰 녹음 버튼 + 타이머 — "한 번의 탭으로 시작"
3. **처리 중 화면**: STT → Diarization → Summary 진행률
4. **결과 화면**: 화자별 전사본 + AI 요약 — 핵심 정보 한눈에
5. **검색/내보내기**: 전체 텍스트 검색 및 PDF 내보내기

---

## Privacy Policy (T-017)

기존 Privacy Policy: [`docs/privacy-policy.md`](privacy-policy.md)

App Store / Google Play 제출 시 위 URL을 외부에서 접근 가능하도록 호스팅 필요:
- GitHub Pages: `https://kiminbean.github.io/voice-to-textnote/privacy-policy.html`
- 또는 앱 내 웹뷰로 표시

### Policy 업데이트 필요사항
- 백그라운드 녹음 데이터 처리 내용 명시
- FCM 토큰 수집 항목 명시 (이미 포함됨)
- 화자 분리(Diarization) 데이터 처리 내용 (이미 포함됨)
