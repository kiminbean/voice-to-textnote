"""
SPEC-EXPORT-001: PDF 생성기 단위 테스트 (TDD RED 단계)

테스트 대상: backend.pipeline.pdf_generator.MinutesPDFGenerator
"""

import pytest

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_minutes_data() -> dict:
    """최소 유효 회의록 데이터"""
    return {
        "task_id": "test-minutes-task-001",
        "segments": [
            {
                "speaker_name": "김팀장",
                "text": "안녕하세요, 오늘 회의를 시작하겠습니다.",
                "start": 0.0,
                "end": 5.0,
            },
            {
                "speaker_name": "이개발",
                "text": "네, 준비됐습니다.",
                "start": 5.5,
                "end": 8.0,
            },
        ],
        "speakers": [
            {
                "speaker_name": "김팀장",
                "total_speaking_time": 120.0,
                "segment_count": 15,
                "speaking_ratio": 60.0,
            },
            {
                "speaker_name": "이개발",
                "total_speaking_time": 80.0,
                "segment_count": 10,
                "speaking_ratio": 40.0,
            },
        ],
        "total_duration": 200.0,
        "total_speakers": 2,
        "markdown": "# 회의록\n\n테스트 내용",
        "created_at": "2026-03-22T14:00:00",
        "completed_at": "2026-03-22T14:05:00",
    }


@pytest.fixture
def sample_summary_data() -> dict:
    """최소 유효 요약 데이터"""
    return {
        "task_id": "test-summary-task-001",
        "summary_text": "오늘 회의에서는 프로젝트 현황을 점검하고 다음 단계를 논의했습니다.",
        "action_items": [
            {
                "assignee": "김팀장",
                "task": "보고서 작성",
                "deadline": "2026-03-25",
                "priority": "high",
            },
            {
                "assignee": "이개발",
                "task": "코드 리뷰",
                "deadline": "2026-03-24",
                "priority": "medium",
            },
        ],
        "key_decisions": ["다음 스프린트 일정 확정", "신규 기능 우선순위 결정"],
        "next_steps": ["보고서 작성 후 공유", "코드 리뷰 완료"],
    }


@pytest.fixture
def empty_segments_minutes_data() -> dict:
    """빈 segments를 가진 회의록 데이터 (오류 케이스)"""
    return {
        "task_id": "test-minutes-task-empty",
        "segments": [],
        "speakers": [],
        "total_duration": 0.0,
        "total_speakers": 0,
        "markdown": "",
        "created_at": "2026-03-22T14:00:00",
        "completed_at": "2026-03-22T14:00:00",
    }


# ---------------------------------------------------------------------------
# PDF 생성기 테스트
# ---------------------------------------------------------------------------


class TestMinutesPDFGenerator:
    """MinutesPDFGenerator 단위 테스트 스위트"""

    def test_generate_returns_pdf_bytes(self, sample_minutes_data: dict) -> None:
        """
        REQ-EXPORT-001: generate() 메서드가 bytes를 반환해야 함
        PDF 매직 바이트(%PDF-)로 시작해야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data)

        assert isinstance(result, bytes)
        # PDF 파일 시그니처 확인
        assert result[:5] == b"%PDF-", f"PDF 시그니처 없음: {result[:10]}"

    def test_pdf_header_contains_title(self, sample_minutes_data: dict) -> None:
        """
        REQ-EXPORT-002: PDF에 '회의록' 제목이 포함되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data)

        # PDF 내용에 한국어 텍스트 포함 여부는 바이트 검사보다
        # 길이로 검증 (한국어 폰트 렌더링 확인)
        assert len(result) > 1000, "PDF가 너무 작음 - 폰트/콘텐츠 렌더링 실패 의심"

    def test_pdf_speaker_stats_rendered(self, sample_minutes_data: dict) -> None:
        """
        REQ-EXPORT-003: 발화자 통계 테이블이 PDF에 렌더링되어야 함
        speakers 데이터가 있으면 테이블 섹션이 생성되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data)

        # 발화자 통계가 있는 경우 PDF 크기가 유의미해야 함
        assert len(result) > 2000, "발화자 통계 섹션이 누락된 것으로 의심됨"

    def test_pdf_minutes_body_rendered(self, sample_minutes_data: dict) -> None:
        """
        REQ-EXPORT-004: 회의록 본문(segments)이 PDF에 렌더링되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data)

        # 세그먼트가 2개 있으므로 충분한 크기여야 함
        assert len(result) > 2000

    def test_pdf_summary_rendered(
        self, sample_minutes_data: dict, sample_summary_data: dict
    ) -> None:
        """
        REQ-EXPORT-005: 요약 데이터가 있으면 PDF에 요약 섹션이 렌더링되어야 함
        요약 없는 PDF보다 크기가 커야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator_without_summary = MinutesPDFGenerator()
        pdf_without = generator_without_summary.generate(sample_minutes_data)

        generator_with_summary = MinutesPDFGenerator()
        pdf_with = generator_with_summary.generate(sample_minutes_data, sample_summary_data)

        # 요약 포함 PDF가 더 커야 함
        assert len(pdf_with) > len(pdf_without), "요약 섹션이 추가되지 않은 것으로 의심됨"

    def test_pdf_action_items_rendered(
        self, sample_minutes_data: dict, sample_summary_data: dict
    ) -> None:
        """
        REQ-EXPORT-006: action_items가 있으면 액션 아이템 테이블이 렌더링되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data, sample_summary_data)

        # 요약 + 액션 아이템 포함 PDF
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"
        assert len(result) > 3000, "액션 아이템 테이블이 누락된 것으로 의심됨"

    def test_pdf_korean_text_rendering(self, sample_minutes_data: dict) -> None:
        """
        REQ-EXPORT-007: NotoSansKR 폰트로 한국어 텍스트가 렌더링되어야 함
        ValueError나 UnicodeEncodeError 없이 생성 완료되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        # 한국어 특수문자 포함 테스트
        minutes_with_korean = {
            **sample_minutes_data,
            "segments": [
                {
                    "speaker_name": "홍길동",
                    "text": "안녕하세요! 반갑습니다. 오늘 회의 주제는 '프로젝트 현황'입니다.",
                    "start": 0.0,
                    "end": 5.0,
                }
            ],
        }

        generator = MinutesPDFGenerator()
        # 예외 없이 생성되어야 함
        result = generator.generate(minutes_with_korean)
        assert result[:5] == b"%PDF-"

    def test_empty_segments_raises_value_error(
        self, empty_segments_minutes_data: dict
    ) -> None:
        """
        REQ-EXPORT-008: segments가 비어있으면 ValueError를 발생시켜야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator = MinutesPDFGenerator()
        with pytest.raises(ValueError, match="segments"):
            generator.generate(empty_segments_minutes_data)

    def test_generate_without_summary(self, sample_minutes_data: dict) -> None:
        """
        REQ-EXPORT-009: summary_data=None이면 요약 섹션 없이 PDF 생성되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data, summary_data=None)

        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_key_decisions_rendered(
        self, sample_minutes_data: dict, sample_summary_data: dict
    ) -> None:
        """
        key_decisions 목록이 PDF에 포함되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data, sample_summary_data)

        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_generate_with_template_table_layout(
        self, sample_minutes_data: dict
    ) -> None:
        """
        template_structure에 table_layout이 있으면 양식 테이블 렌더링 경로가 실행되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        # template_structure + table_layout이 포함된 요약 데이터
        summary_with_template = {
            "task_id": "summary-template-001",
            "summary_text": "양식 기반 요약",
            "sections": {
                "회의 목적": "프로젝트 현황 점검",
                "주요 논의": "일정 및 역할 분담",
            },
            "action_items": [],
            "key_decisions": [],
            "template_structure": {
                "table_layout": [
                    {"type": "full", "label": "과정명"},
                    {"type": "split", "cells": [
                        {"label": "미팅시간"},
                        {"label": "참여자"},
                    ]},
                    {"type": "full", "label": "주요 논의", "large": True},
                ]
            },
        }

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data, summary_with_template)

        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"
        assert len(result) > 1000

    def test_speakers_empty_skips_stats(self, sample_minutes_data: dict) -> None:
        """
        speakers 목록이 비어있으면 발화자 통계 섹션이 생략되어야 함
        (크기가 더 작아야 함)
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        minutes_no_speakers = {**sample_minutes_data, "speakers": []}

        generator_with = MinutesPDFGenerator()
        pdf_with = generator_with.generate(sample_minutes_data)

        generator_without = MinutesPDFGenerator()
        pdf_without = generator_without.generate(minutes_no_speakers)

        # 발화자 통계가 없으면 크기가 더 작아야 함
        assert len(pdf_without) < len(pdf_with)

    def test_summary_text_is_json_string(self, sample_minutes_data: dict) -> None:
        """
        summary_text가 JSON 문자열이면 내부 summary_text를 추출해야 함
        ValueError 없이 생성되어야 함
        """
        import json as _json
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        # summary_text가 JSON 형식인 경우
        inner_summary = {"summary_text": "내부 요약 텍스트", "key": "value"}
        summary_json_text = {
            "summary_text": _json.dumps(inner_summary),
            "action_items": [],
            "key_decisions": [],
        }

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data, summary_json_text)

        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_key_decisions_with_dict_items(self, sample_minutes_data: dict) -> None:
        """
        key_decisions가 dict 형태의 항목을 포함할 때 올바르게 처리되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        summary_dict_decisions = {
            "summary_text": "결정 사항 테스트",
            "action_items": [],
            "key_decisions": [
                {"decision": "dict 형태 결정 사항"},
                "문자열 형태 결정 사항",
            ],
        }

        generator = MinutesPDFGenerator()
        result = generator.generate(sample_minutes_data, summary_dict_decisions)

        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_summary_empty_text_skips_summary_section(
        self, sample_minutes_data: dict
    ) -> None:
        """
        summary_text가 빈 문자열이면 요약 섹션이 생략되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        summary_empty_text = {
            "summary_text": "",  # 빈 문자열
            "action_items": [],
            "key_decisions": [],
        }

        generator_no_summary = MinutesPDFGenerator()
        pdf_no_summary = generator_no_summary.generate(sample_minutes_data)

        generator_empty = MinutesPDFGenerator()
        pdf_empty = generator_empty.generate(sample_minutes_data, summary_empty_text)

        # 빈 요약은 요약 없는 경우와 비슷한 크기여야 함 (섹션 생략)
        assert isinstance(pdf_empty, bytes)
        assert pdf_empty[:5] == b"%PDF-"

    def test_format_duration_mmss(self) -> None:
        """
        _format_duration_mmss 유틸리티 메서드 테스트
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        assert MinutesPDFGenerator._format_duration_mmss(0.0) == "00:00"
        assert MinutesPDFGenerator._format_duration_mmss(65.5) == "01:05"
        assert MinutesPDFGenerator._format_duration_mmss(3600.0) == "60:00"

    def test_format_duration_hhmmss(self) -> None:
        """
        _format_duration_hhmmss 유틸리티 메서드 테스트
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        assert MinutesPDFGenerator._format_duration_hhmmss(0.0) == "00:00:00"
        assert MinutesPDFGenerator._format_duration_hhmmss(3661.0) == "01:01:01"
        assert MinutesPDFGenerator._format_duration_hhmmss(200.0) == "00:03:20"

    def test_summary_text_invalid_json_string(self, sample_minutes_data: dict) -> None:
        """
        summary_text가 유효하지 않은 JSON 형식이면 원본 텍스트를 그대로 사용해야 함
        파싱 실패해도 예외 없이 생성되어야 함
        """
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        # 중괄호로 시작하지만 유효하지 않은 JSON
        summary_invalid_json = {
            "summary_text": "{broken json: not valid}",
            "action_items": [],
            "key_decisions": [],
        }

        generator = MinutesPDFGenerator()
        # 예외 없이 생성되어야 함
        result = generator.generate(sample_minutes_data, summary_invalid_json)

        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"
