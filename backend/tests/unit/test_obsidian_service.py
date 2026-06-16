"""SPEC-OBSIDIAN-001: ObsidianService 회귀 테스트."""


import pytest

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
            {"speaker_id": "SPEAKER_00", "speaker_name": "Speaker 1", "total_speaking_time": 5.0, "segment_count": 1, "speaking_ratio": 50.0},
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
    }


@pytest.fixture
def sentiment_data():
    return {
        "overall_sentiment": "positive",
        "overall_emotion": "joy",
        "speakers": [{"speaker": "Speaker 1", "dominant_emotion": "joy", "positive_ratio": 0.8, "neutral_ratio": 0.2, "negative_ratio": 0.0}],
    }


@pytest.fixture
def tone_data():
    return {
        "overall_tone": "calm",
        "speakers": [{"speaker": "Speaker 1", "dominant_tone": "calm", "avg_pitch": 150.0}],
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
            service.compute_file_path(
                str(tmp_vault), "../../../etc", "{{date}}", meeting_data
            )

    def test_traversal_in_filename_blocked(self, service, tmp_vault, meeting_data):
        with pytest.raises(ValueError, match="탐색"):
            service.compute_file_path(
                str(tmp_vault), "{{date}}", "../../passwd", meeting_data
            )

    def test_vault_confinement_relative_to(self, service, tmp_path, meeting_data):
        vault_a = tmp_path / "vault"
        (vault_a / ".obsidian").mkdir(parents=True)
        vault_b = tmp_path / "vault_evil"
        (vault_b / ".obsidian").mkdir(parents=True)
        path = service.compute_file_path(
            str(vault_a), "{{date}}", "{{title}}", meeting_data
        )
        assert str(path).startswith(str(vault_a))
        assert str(path).startswith(str(vault_b)) is False

    def test_empty_filename_fallback(self, service, tmp_vault, meeting_data):
        path = service.compute_file_path(
            str(tmp_vault), "{{date}}", "", meeting_data
        )
        assert path.name == "untitled.md"


class TestBuildFrontmatter:
    def test_valid_yaml(self, service, meeting_data, minutes_data, summary_data, sentiment_data, tone_data):
        import yaml

        fm_str = service.build_frontmatter(meeting_data, minutes_data, summary_data, sentiment_data, tone_data)
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
            meeting_data, minutes_data, None, None, None,
            custom={"additional_tags": ["work", "project-x"]},
        )
        import yaml

        parsed = yaml.safe_load(fm_str[4:-4])
        assert "work" in parsed["tags"]
        assert "project-x" in parsed["tags"]

    def test_custom_tags_string_rejected(self, service, meeting_data, minutes_data):
        fm_str = service.build_frontmatter(
            meeting_data, minutes_data, None, None, None,
            custom={"additional_tags": "not_a_list"},
        )
        import yaml

        parsed = yaml.safe_load(fm_str[4:-4])
        assert "n" not in parsed["tags"]

    def test_custom_field_key_injection_blocked(self, service, meeting_data, minutes_data):
        fm_str = service.build_frontmatter(
            meeting_data, minutes_data, None, None, None,
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
    def test_all_sections(self, service, meeting_data, minutes_data, summary_data, sentiment_data, tone_data):
        body = service.build_note_body(meeting_data, minutes_data, summary_data, sentiment_data, tone_data)
        assert "# 테스트 회의" in body
        assert "## 📋 개요" in body
        assert "테스트 요약입니다." in body
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
