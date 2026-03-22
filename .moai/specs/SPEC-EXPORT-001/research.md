# SPEC-EXPORT-001: 회의록 PDF 내보내기 리서치

## 1. 현재 데이터 흐름

### 1.1 회의록 result_data (minutes_task.py)
- segments: [{speaker_name, text, start, end}] - 화자별 발화
- speakers: [{speaker_name, total_speaking_time, speaking_ratio}] - 화자 통계
- markdown: 마크다운 형식 회의록 (존재 시 우선 사용)
- total_duration, total_speakers

### 1.2 요약 result_data (summary_task.py)
- summary_text: AI 요약 전문
- action_items: [{assignee, task, deadline, priority}]
- key_decisions: [str]
- next_steps: [str]

### 1.3 결과 조회 API
- GET /api/v1/minutes/{task_id} -> MinutesResponse
- GET /api/v1/summaries/{task_id} -> SummaryResponse
- Meeting 모델에 minutesTaskId, summaryTaskId 보유

## 2. Flutter 결과 화면 (result_screen.dart)
- 3탭 구조: 회의록, AI 요약, 액션 아이템
- minutesResultProvider, summaryResultProvider 사용
- 현재 공유/내보내기 기능 없음

## 3. 기존 의존성
- pdfplumber (읽기 전용), python-docx (읽기 전용) - PDF 생성 라이브러리 없음
- Flutter: path_provider, file_picker 존재, PDF/share 패키지 없음
- 파일 다운로드 엔드포인트 없음 (JSON API만 존재)

## 4. 권장 접근법: 백엔드 PDF 생성

**이유:**
1. 한국어 렌더링: 서버에 NotoSansKR 폰트 1회 설정으로 해결
2. 기존 아키텍처 정합성: Celery 패턴과 동일
3. 데이터 접근: Redis에서 minutes + summary 직접 접근 가능

**PDF 라이브러리:** fpdf2 (가볍고 TTF 등록으로 한국어 해결)

## 5. 리스크
- 한국어 폰트: fpdf2 + NotoSansKR TTF 등록 필요
- Redis TTL 24h: 만료 후 DB fallback 필요
- 임시 파일 관리: settings.temp_dir + 기존 보존 정책 활용

## 6. 파일 변경 범위
- Backend 신규: pdf_generator.py, export.py (API), export.py (스키마)
- Backend 수정: main.py, config.py, pyproject.toml, requirements-ubuntu.txt
- Flutter 신규: export_api.dart
- Flutter 수정: result_screen.dart (공유 버튼), pubspec.yaml (share_plus)

## 7. PDF 내용 구성
1. 헤더 (제목, 날짜, 총 시간)
2. 화자 통계 (표)
3. 회의록 본문 ([시간] 화자: 텍스트)
4. AI 요약
5. 주요 결정사항
6. 다음 단계
7. 액션 아이템 (표)
