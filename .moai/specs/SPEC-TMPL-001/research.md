# SPEC-TMPL-001 Research: 회의록 양식 업로드 + 양식 기반 회의록 생성

## 1. Architecture Analysis

### Backend 현황

**요약 생성 흐름**:
```
POST /summaries → Celery task → SummaryGenerator.build_prompt() → ZAI API → JSON 파싱 → Redis 캐싱
```

**프롬프트** (`backend/pipeline/summary_generator.py:30-77`):
- `build_prompt(segments, speaker_stats)` — 하드코딩된 4개 항목 요청
- 출력: summary_text, action_items, key_decisions, next_steps
- JSON 형식 지시문 포함

**파일 업로드 선례** (`backend/app/api/v1/transcription.py:44`):
- `UploadFile = File(...)` + `multipart/form-data` 패턴 사용 중
- 오디오 파일 업로드 → `storage/temp/` 저장

**설정** (`backend/app/config.py`):
- `temp_dir: Path("./storage/temp")`, `results_dir: Path("./storage/results")`
- `templates_dir` 없음 → 신규 추가 필요

**Celery 태스크** (`backend/workers/tasks/summary_task.py`):
- `summary_task(task_id, minutes_task_id, max_tokens)` — template_id 파라미터 없음
- Redis에서 회의록 조회 → SummaryGenerator 호출 → 결과 캐싱

### Flutter 현황

**홈 화면** (`client/lib/screens/home_screen.dart`):
- AppBar + 미팅 목록 + FAB(녹음 시작)
- 템플릿 관리 진입점 없음

**API 서비스 패턴** (`client/lib/services/transcription_api.dart`):
- Dio + MultipartFile.fromFile() + FormData 업로드 패턴 존재

**파일 선택**: `file_picker` 패키지 미사용, pubspec.yaml에 없음

## 2. 신규 Python 패키지

| 포맷 | 패키지 | 용도 |
|------|--------|------|
| PDF | `pdfplumber` | PDF 텍스트/표 추출 |
| DOCX | `python-docx` | Word 문단/표/스타일 추출 |

## 3. 데이터 흐름 설계

```
[Flutter] 양식 파일 선택 (file_picker)
  → POST /api/v1/templates (multipart/form-data)
  → [Backend] 파일 저장 (storage/templates/{id}/)
  → [Backend] 구조 추출 (TemplateParser)
  → [Backend] Redis에 메타데이터 + 구조 저장
  → 응답: {template_id, name, format, structure}

[Flutter] 요약 생성 시 template_id 선택
  → POST /api/v1/summaries {minutes_task_id, template_id}
  → [Celery] Redis에서 템플릿 구조 로드
  → [Celery] SummaryGenerator.build_prompt(segments, stats, template_structure)
  → [ZAI] 템플릿 양식에 맞춘 응답
  → Redis 캐싱
```

## 4. 템플릿 구조 추출 전략

**DOCX**: python-docx로 문단(Paragraph) + 표(Table) 추출, 제목 스타일 감지
**PDF**: pdfplumber로 텍스트 + 표 추출, 섹션 경계 감지 (폰트 크기/볼드)

추출 결과 (TemplateStructure):
```json
{
  "sections": ["회의 개요", "참석자", "안건", "토의 내용", "결정 사항", "액션 아이템"],
  "fields": {"회의명": "text", "일시": "date", "장소": "text", "참석자": "list"},
  "has_table": true,
  "raw_text_preview": "처음 500자..."
}
```

## 5. Risks

- DOCX/PDF 구조 추출 정확도: AI에 구조 추출을 보조 위임 가능
- 프롬프트 길이: 템플릿 구조를 간결하게 압축
- 파일 크기: 10MB 제한
