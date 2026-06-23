"""SPEC-OBSIDIAN-001: ObsidianService 회귀 테스트."""

import pytest

import backend.services.obsidian_service as obsidian_module
from backend.services.obsidian_service import ObsidianService


@pytest.fixture
def service():
    return ObsidianService()


@pytest.fixture
def tmp_vault(tmp_path):
    vault = tmp_path / "TestVault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


@pytest.fixture
def meeting_data():
    return {
        "meeting_id": "test-123",
        "title": "테스트 회의",
        "created_at": "2026-06-16T10:30:00Z",
        "duration": 600,
    }


@pytest.fixture
def minutes_data():
    return {
        "segments": [
            {"speaker_name": "Speaker 1", "text": "안녕하세요", "start": 0.0, "end": 5.0},
            {"speaker_name": "Speaker 2", "text": "반갑습니다", "start": 5.0, "end": 10.0},
        ],
        "speakers": [
            {
                "speaker_id": "SPEAKER_00",
                "speaker_name": "Speaker 1",
                "total_speaking_time": 5.0,
                "segment_count": 1,
                "speaking_ratio": 50.0,
            },
        ],
        "total_duration": 600,
        "created_at": "2026-06-16T10:30:00Z",
    }


@pytest.fixture
def summary_data():
    return {
        "summary_text": "테스트 요약입니다.",
        "action_items": [{"task": "작업 A", "assignee": "Speaker 1", "deadline": "2026-06-20"}],
        "key_decisions": ["결정 1"],
        "next_steps": ["다음 단계 1"],
        "translations": {
            "en": {
                "source_type": "summary",
                "target_language": "en",
                "translated_text": "English meeting summary",
            }
        },
    }


@pytest.fixture
def sentiment_data():
    return {
        "overall_sentiment": "positive",
        "overall_emotion": "joy",
        "speakers": [
            {
                "speaker": "Speaker 1",
                "dominant_emotion": "joy",
                "positive_ratio": 0.8,
                "neutral_ratio": 0.2,
                "negative_ratio": 0.0,
            }
        ],
    }


@pytest.fixture
def tone_data():
    return {
        "overall_tone": "calm",
        "speakers": [{"speaker": "Speaker 1", "dominant_tone": "calm", "avg_pitch": 150.0}],
    }


@pytest.fixture
def study_pack_data():
    return {
        "mode": "lecture",
        "study_notes": "테스트 회의를 복습하기 위한 학습 노트입니다.",
        "key_concepts": [{"term": "테스트 개념", "explanation": "핵심 설명입니다."}],
        "flashcards": [{"front": "테스트 질문?", "back": "테스트 답변"}],
        "quiz_questions": [{"question": "복습 문제?", "answer": "복습 답변", "difficulty": "easy"}],
    }


class TestValidateVault:
    def test_valid_vault(self, service, tmp_vault):
        result = service.validate_vault(str(tmp_vault))
        assert result["valid"] is True
        assert result["vault_name"] == "TestVault"
        assert result["obsidian_folder_exists"] is True
        assert result["is_symlink"] is False

    def test_missing_obsidian_folder(self, service, tmp_path):
        result = service.validate_vault(str(tmp_path / "NoVault"))
        assert result["valid"] is False
        assert result["obsidian_folder_exists"] is False

    def test_symlink_rejected(self, service, tmp_path, tmp_vault):
        link = tmp_path / "VaultLink"
        link.symlink_to(tmp_vault)
        result = service.validate_vault(str(link))
        assert result["valid"] is False
        assert result["is_symlink"] is True


class TestComputeFilePath:
    def test_normal_path(self, service, tmp_vault, meeting_data):
        path = service.compute_file_path(
            str(tmp_vault), "Meetings/{{date}}", "{{date}}_{{title}}", meeting_data
        )
        assert "Meetings/2026-06-16" in str(path)
        assert path.name == "2026-06-16_테스트_회의.md"
        assert str(path).startswith(str(tmp_vault))

    def test_traversal_in_folder_blocked(self, service, tmp_vault, meeting_data):
        with pytest.raises(ValueError, match="탐색"):
            service.compute_file_path(str(tmp_vault), "../../../etc", "{{date}}", meeting_data)

    def test_traversal_in_filename_blocked(self, service, tmp_vault, meeting_data):
        with pytest.raises(ValueError, match="탐색"):
            service.compute_file_path(str(tmp_vault), "{{date}}", "../../passwd", meeting_data)

    def test_vault_confinement_relative_to(self, service, tmp_path, meeting_data):
        vault_a = tmp_path / "vault"
        (vault_a / ".obsidian").mkdir(parents=True)
        vault_b = tmp_path / "vault_evil"
        (vault_b / ".obsidian").mkdir(parents=True)
        path = service.compute_file_path(str(vault_a), "{{date}}", "{{title}}", meeting_data)
        assert str(path).startswith(str(vault_a))
        assert str(path).startswith(str(vault_b)) is False

    def test_empty_filename_fallback(self, service, tmp_vault, meeting_data):
        path = service.compute_file_path(str(tmp_vault), "{{date}}", "", meeting_data)
        assert path.name == "untitled.md"

    def test_resolved_symlink_folder_cannot_escape_vault(
        self, service, tmp_vault, tmp_path, meeting_data
    ):
        outside = tmp_path / "outside"
        outside.mkdir()
        (tmp_vault / "linked").symlink_to(outside)

        with pytest.raises(ValueError, match="vault 외부"):
            service.compute_file_path(str(tmp_vault), "linked", "{{title}}", meeting_data)


class TestDateParsing:
    def test_missing_datetime_returns_none(self, service):
        assert service._parse_datetime("") is None

    def test_iso_datetime_fallback_and_invalid_datetime(self, service):
        parsed = service._parse_datetime("2026-06-16T10:30:00+09:00")

        assert parsed is not None
        assert parsed.hour == 10
        assert service._parse_datetime("not-a-date") is None


class TestBuildFrontmatter:
    def test_valid_yaml(
        self, service, meeting_data, minutes_data, summary_data, sentiment_data, tone_data
    ):
        import yaml  # type: ignore[import-untyped]

        fm_str = service.build_frontmatter(
            meeting_data, minutes_data, summary_data, sentiment_data, tone_data
        )
        assert fm_str.startswith("---\n")
        assert fm_str.endswith("\n---")

        yaml_content = fm_str[4:-4]
        parsed = yaml.safe_load(yaml_content)

        assert parsed["type"] == "meeting"
        assert parsed["date"] == "2026-06-16"
        assert parsed["title"] == "테스트 회의"
        assert "voice-to-textnote" in parsed["tags"]
        assert parsed["sentiment"] == "positive"
        assert parsed["overall_tone"] == "calm"

    def test_custom_tags(self, service, meeting_data, minutes_data):
        fm_str = service.build_frontmatter(
            meeting_data,
            minutes_data,
            None,
            None,
            None,
            custom={"additional_tags": ["work", "project-x"]},
        )
        import yaml

        parsed = yaml.safe_load(fm_str[4:-4])
        assert "work" in parsed["tags"]
        assert "project-x" in parsed["tags"]

    def test_custom_tags_string_rejected(self, service, meeting_data, minutes_data):
        fm_str = service.build_frontmatter(
            meeting_data,
            minutes_data,
            None,
            None,
            None,
            custom={"additional_tags": "not_a_list"},
        )
        import yaml

        parsed = yaml.safe_load(fm_str[4:-4])
        assert "n" not in parsed["tags"]

    def test_custom_field_key_injection_blocked(self, service, meeting_data, minutes_data):
        fm_str = service.build_frontmatter(
            meeting_data,
            minutes_data,
            None,
            None,
            None,
            custom={"custom_fields": {"malicious:key": "value", "good_key": "good_value"}},
        )
        import yaml

        parsed = yaml.safe_load(fm_str[4:-4])
        assert "good_key" in parsed
        assert "malicious:key" not in parsed

    def test_no_sections_when_missing(self, service, meeting_data):
        fm_str = service.build_frontmatter(meeting_data, None, None, None, None)
        import yaml

        parsed = yaml.safe_load(fm_str[4:-4])
        assert "participants" not in parsed
        assert "sentiment" not in parsed


class TestBuildNoteBody:
    def test_all_sections(
        self,
        service,
        meeting_data,
        minutes_data,
        summary_data,
        sentiment_data,
        tone_data,
        study_pack_data,
    ):
        body = service.build_note_body(
            meeting_data,
            minutes_data,
            summary_data,
            sentiment_data,
            tone_data,
            study_pack_data,
        )
        assert "# 테스트 회의" in body
        assert "## 📋 개요" in body
        assert "테스트 요약입니다." in body
        assert "## 🎓 학습팩" in body
        assert "테스트 개념" in body
        assert "테스트 질문?" in body
        assert "복습 문제?" in body
        assert "## 🌐 번역" in body
        assert "English meeting summary" in body
        assert "## ✅ 액션 아이템" in body
        assert "작업 A" in body
        assert "## 📌 주요 결정" in body
        assert "## 📝 회의록" in body
        assert "안녕하세요" in body
        assert "## 📊 감정 분석" in body
        assert "## 🎵 톤 분석" in body
        assert "## 🔗 링크" in body

    def test_no_analysis_sections_when_missing(self, service, meeting_data, minutes_data):
        body = service.build_note_body(meeting_data, minutes_data, None, None, None)
        assert "## 📊 감정 분석" not in body
        assert "## 🎵 톤 분석" not in body
        assert "## 📋 개요" not in body

    def test_empty_transcript_is_omitted(self, service, meeting_data):
        body = service.build_note_body(
            meeting_data,
            {"segments": []},
            None,
            None,
            None,
        )

        assert "## 📝 회의록" not in body
        assert "## 🔗 링크" in body

    def test_empty_study_pack_is_omitted(self, service, meeting_data, minutes_data):
        body = service.build_note_body(
            meeting_data,
            minutes_data,
            None,
            None,
            None,
            {"key_concepts": [], "flashcards": [], "quiz_questions": [], "study_notes": ""},
        )

        assert "## 🎓 학습팩" not in body

    def test_empty_translations_are_omitted(self, service, meeting_data, minutes_data):
        body = service.build_note_body(
            meeting_data,
            {**minutes_data, "translations": {"bad": "not-a-dict"}},
            {"translations": {"en": {"translated_text": "  "}}},
            None,
            None,
        )

        assert "## 🌐 번역" not in body

    def test_study_pack_markdown_skips_invalid_items_and_keeps_partial_content(self, service):
        markdown = service._build_study_pack_md(
            {
                "key_concepts": ["bad", {"term": "용어만"}],
                "flashcards": ["bad", {"front": "앞면만"}],
                "quiz_questions": ["bad", {"answer": "답만"}],
            }
        )

        assert "**용어만**" in markdown
        assert "**Q.** 앞면만" in markdown
        assert "정답: 답만" in markdown

    def test_translation_markdown_deduplicates_cached_aliases(self, service):
        markdown = service._build_translation_md(
            {
                "translations": {
                    "en": {
                        "source_type": "summary",
                        "target_language": "en",
                        "translated_text": "English meeting summary",
                    },
                    "summary:en": {
                        "source_type": "summary",
                        "target_language": "en",
                        "translated_text": "English meeting summary",
                    },
                    "bad": "not-a-dict",
                }
            },
            {
                "translations": {
                    "minutes:ja": {
                        "source_type": "minutes",
                        "target_language": "ja",
                        "translated_text": "日本語の議事録",
                    }
                }
            },
        )

        assert "### en (요약)" in markdown
        assert markdown.count("English meeting summary") == 1
        assert "### ja (회의록)" in markdown
        assert "日本語の議事録" in markdown


class TestAtomicWrite:
    def test_write_creates_file(self, service, tmp_path):
        target = tmp_path / "note.md"
        service.atomic_write(target, "# Test\nContent")
        assert target.exists()
        assert target.read_text() == "# Test\nContent"

    def test_overwrite_existing(self, service, tmp_path):
        target = tmp_path / "note.md"
        target.write_text("old")
        service.atomic_write(target, "new")
        assert target.read_text() == "new"

    def test_exist_ok_false_skips_existing(self, service, tmp_path):
        target = tmp_path / "note.md"
        target.write_text("original")
        result = service.atomic_write(target, "new", exist_ok=False)
        assert result is False
        assert target.read_text() == "original"

    def test_exist_ok_false_creates_new(self, service, tmp_path):
        target = tmp_path / "note.md"
        result = service.atomic_write(target, "new", exist_ok=False)
        assert result is True
        assert target.read_text() == "new"

    def test_no_partial_file_on_failure(self, service, tmp_path):
        target = tmp_path / "note.md"
        service.atomic_write(target, "good content")
        assert target.exists()
        assert target.read_text() == "good content"
        assert not list(tmp_path.glob(".obs_*.tmp"))

    def test_concurrent_exist_ok_false_only_one_succeeds(self, service, tmp_path):
        import threading

        target = tmp_path / "race.md"
        results = []

        def writer(content):
            r = service.atomic_write(target, content, exist_ok=False)
            results.append(r)

        t1 = threading.Thread(target=writer, args=("writer1",))
        t2 = threading.Thread(target=writer, args=("writer2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results.count(True) == 1
        assert results.count(False) == 1

    def test_temp_file_cleanup_after_exist_ok_false_skip(self, service, tmp_path):
        target = tmp_path / "note.md"
        target.write_text("original")
        service.atomic_write(target, "new", exist_ok=False)
        assert not list(tmp_path.glob(".obs_*.tmp"))

    def test_temp_cleanup_failure_does_not_mask_atomic_write_error(
        self, service, tmp_path, monkeypatch
    ):
        target = tmp_path / "note.md"
        tmp_files = []
        original_unlink = obsidian_module.os.unlink

        def fail_replace(_tmp_path, _target):
            raise RuntimeError("replace failed")

        def fail_unlink(path):
            tmp_files.append(path)
            raise OSError("cleanup failed")

        monkeypatch.setattr(obsidian_module.os, "replace", fail_replace)
        monkeypatch.setattr(obsidian_module.os, "unlink", fail_unlink)

        try:
            with pytest.raises(RuntimeError, match="replace failed"):
                service.atomic_write(target, "content")
        finally:
            for tmp_file in tmp_files:
                if obsidian_module.Path(tmp_file).exists():
                    original_unlink(tmp_file)


class TestObsidianUriAndCompose:
    def test_build_obsidian_uri_strips_markdown_suffix_and_encodes_path(self, service, tmp_vault):
        note = tmp_vault / "Meetings" / "2026 06" / "회의록.md"
        note.parent.mkdir(parents=True)
        note.write_text("note")

        uri = service.build_obsidian_uri(str(tmp_vault), note)

        assert (
            uri
            == "obsidian://open?vault=TestVault&file=Meetings%2F2026%2006%2F%ED%9A%8C%EC%9D%98%EB%A1%9D"
        )

    def test_compose_note_joins_frontmatter_and_body(self, service, monkeypatch, meeting_data):
        calls = []

        def fake_frontmatter(*args, **kwargs):
            calls.append(("frontmatter", args, kwargs))
            return "---\ntitle: test\n---"

        def fake_body(*args):
            calls.append(("body", args, {}))
            return "# Body"

        monkeypatch.setattr(service, "build_frontmatter", fake_frontmatter)
        monkeypatch.setattr(service, "build_note_body", fake_body)

        note = service.compose_note(
            meeting_data,
            None,
            None,
            None,
            None,
            None,
            frontmatter_custom={"custom_fields": {"project": "alpha"}},
        )

        assert note == "---\ntitle: test\n---\n\n# Body"
        assert calls[0][0] == "frontmatter"
        assert calls[0][2] == {"custom": {"custom_fields": {"project": "alpha"}}}
        assert calls[1][0] == "body"


class TestSafeJsonLoad:
    def test_none_returns_none(self):
        from backend.app.api.v1.integrations.obsidian import _safe_json_load

        assert _safe_json_load(None) is None

    def test_empty_string_returns_none(self):
        from backend.app.api.v1.integrations.obsidian import _safe_json_load

        assert _safe_json_load("") is None

    def test_malformed_json_returns_none(self):
        from backend.app.api.v1.integrations.obsidian import _safe_json_load

        assert _safe_json_load("{broken") is None

    def test_list_returns_none(self):
        from backend.app.api.v1.integrations.obsidian import _safe_json_load

        assert _safe_json_load("[1,2,3]") is None

    def test_string_returns_none(self):
        from backend.app.api.v1.integrations.obsidian import _safe_json_load

        assert _safe_json_load('"hello"') is None

    def test_number_returns_none(self):
        from backend.app.api.v1.integrations.obsidian import _safe_json_load

        assert _safe_json_load("42") is None

    def test_valid_dict_returns_dict(self):
        from backend.app.api.v1.integrations.obsidian import _safe_json_load

        result = _safe_json_load('{"key": "value"}')
        assert result == {"key": "value"}

    def test_malformed_bytes_returns_none(self):
        from backend.app.api.v1.integrations.obsidian import _safe_json_load

        assert _safe_json_load(b"\xff") is None
