"""SPEC-OBSIDIAN-001: Obsidian vault 연계 서비스.

Direct file write 방식으로 vault에 마크다운 노트를 생성한다.
백엔드와 vault가 동일 머신에 있다는 전제하에 파일 시스템 직접 접근.
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TRAVERSAL_PATTERN = re.compile(r"\.\.")


class ObsidianService:
    """Vault 검증, 경로 계산, 마크다운 조합, atomic write 담당."""

    def validate_vault(self, vault_path: str) -> dict[str, Any]:
        """REQ-OBS-001: vault 경로 검증.

        Returns:
            {valid, vault_name, obsidian_folder_exists, writable, is_symlink}
        """
        raw_path = Path(vault_path).expanduser()
        is_symlink = raw_path.is_symlink()
        path = raw_path.resolve()

        obsidian_exists = (path / ".obsidian").is_dir()
        writable = os.access(path, os.W_OK) if path.exists() else False
        valid = obsidian_exists and writable and not is_symlink

        return {
            "valid": valid,
            "vault_name": path.name if path.exists() else "",
            "obsidian_folder_exists": obsidian_exists,
            "writable": writable,
            "is_symlink": is_symlink,
        }

    def compute_file_path(
        self,
        vault_path: str,
        folder_pattern: str,
        filename_pattern: str,
        meeting_data: dict[str, Any],
    ) -> Path:
        """REQ-OBS-002/003: 폴더 및 파일명 패턴 변수 치환."""
        variables = self._extract_pattern_variables(meeting_data)

        folder_rel = self._substitute_pattern(folder_pattern, variables)
        filename_rel = self._substitute_pattern(filename_pattern, variables)
        filename_rel = self._sanitize_filename(filename_rel)

        if not filename_rel.endswith(".md"):
            filename_rel += ".md"

        self._assert_no_traversal(folder_rel)
        self._assert_no_traversal(filename_rel)

        vault = Path(vault_path).expanduser().resolve()
        folder = vault / folder_rel if folder_rel else vault
        file_path = folder / filename_rel

        resolved = file_path.resolve()
        try:
            resolved.relative_to(vault)
        except ValueError as e:
            raise ValueError("경로가 vault 외부로 벗어났습니다") from e

        return resolved

    def _extract_pattern_variables(self, meeting_data: dict[str, Any]) -> dict[str, str]:
        created_at = meeting_data.get("created_at", "")
        dt = self._parse_datetime(created_at)

        title = str(meeting_data.get("title", "회의록"))
        meeting_id = str(meeting_data.get("meeting_id", ""))

        return {
            "date": dt.strftime("%Y-%m-%d") if dt else "unknown-date",
            "year": dt.strftime("%Y") if dt else "unknown",
            "month": dt.strftime("%m") if dt else "unknown",
            "time": dt.strftime("%H%M") if dt else "unknown",
            "title": title,
            "meeting_id": meeting_id,
            "type": "meeting",
        }

    def _parse_datetime(self, raw: str) -> datetime | None:
        if not raw:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f+00:00",
            "%Y-%m-%dT%H:%M:%S+00:00",
        ):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _substitute_pattern(self, pattern: str, variables: dict[str, str]) -> str:
        result = pattern
        for key, value in variables.items():
            result = result.replace("{{" + key + "}}", self._sanitize_segment(value))
        return result.strip("/")

    def _sanitize_segment(self, value: str) -> str:
        return _FORBIDDEN_CHARS.sub("_", value).strip()

    def _sanitize_filename(self, name: str) -> str:
        cleaned = _FORBIDDEN_CHARS.sub("_", name).strip()
        cleaned = re.sub(r"\s+", "_", cleaned)
        if not cleaned or cleaned == ".md":
            cleaned = "untitled"
        return cleaned[:100]

    def _assert_no_traversal(self, value: str) -> None:
        if _TRAVERSAL_PATTERN.search(value):
            raise ValueError(f"경로 탐색 패턴이 감지되었습니다: {value}")

    def build_frontmatter(
        self,
        meeting_data: dict[str, Any],
        minutes_data: dict[str, Any] | None,
        summary_data: dict[str, Any] | None,
        sentiment_data: dict[str, Any] | None,
        tone_data: dict[str, Any] | None,
        custom: dict[str, Any] | None = None,
    ) -> str:
        """REQ-OBS-004: YAML frontmatter 생성 (yaml.safe_dump 기반)."""
        import yaml  # type: ignore[import-untyped]

        created_at = meeting_data.get("created_at", "")
        dt = self._parse_datetime(created_at)

        participants = self._extract_participants(minutes_data)
        tags = ["voice-to-textnote", "meetings"]
        if custom and isinstance(custom.get("additional_tags"), list):
            tags.extend(str(t) for t in custom["additional_tags"])

        fm: dict[str, Any] = {"type": "meeting"}

        if dt:
            fm["date"] = dt.strftime("%Y-%m-%d")
            fm["time"] = dt.strftime("%H:%M")

        fm["title"] = str(meeting_data.get("title", "회의록"))

        duration = meeting_data.get("duration")
        if duration is not None:
            fm["duration_seconds"] = int(duration)

        if participants:
            fm["participants"] = [f"[[{p}]]" for p in participants]

        fm["tags"] = tags
        fm["source"] = "voice-to-textnote"

        meeting_id = meeting_data.get("meeting_id") or meeting_data.get("task_id")
        if meeting_id:
            fm["meeting_id"] = str(meeting_id)

        if sentiment_data:
            overall = sentiment_data.get("overall_sentiment")
            if overall:
                fm["sentiment"] = str(overall)
            emotion = sentiment_data.get("overall_emotion")
            if emotion:
                fm["overall_emotion"] = str(emotion)

        if tone_data:
            overall_tone = tone_data.get("overall_tone")
            if overall_tone:
                fm["overall_tone"] = str(overall_tone)

        if summary_data and summary_data.get("action_items"):
            fm["action_item_count"] = len(summary_data["action_items"])

        if custom and isinstance(custom.get("custom_fields"), dict):
            for k, v in custom["custom_fields"].items():
                if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", str(k)):
                    fm[str(k)] = str(v)

        yaml_text = yaml.safe_dump(
            fm,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ).strip()

        return f"---\n{yaml_text}\n---"

    def _extract_participants(self, minutes_data: dict[str, Any] | None) -> list[str]:
        if not minutes_data:
            return []
        speakers = minutes_data.get("speakers") or []
        names: list[str] = []
        for sp in speakers:
            name = sp.get("speaker_name") or sp.get("speaker_id")
            if name:
                names.append(str(name))
        seen: set[str] = set()
        unique: list[str] = []
        for n in names:
            if n not in seen:
                seen.add(n)
                unique.append(n)
        return unique

    def build_note_body(
        self,
        meeting_data: dict[str, Any],
        minutes_data: dict[str, Any] | None,
        summary_data: dict[str, Any] | None,
        sentiment_data: dict[str, Any] | None,
        tone_data: dict[str, Any] | None,
        study_pack_data: dict[str, Any] | None = None,
        mind_map_data: dict[str, Any] | None = None,
        sales_brief_data: dict[str, Any] | None = None,
    ) -> str:
        """REQ-OBS-005: 노트 본문 섹션 생성."""
        title = meeting_data.get("title", "회의록")
        sections: list[str] = []
        sections.append(f"# {title}\n")

        if summary_data and summary_data.get("summary_text"):
            sections.append("## 📋 개요\n")
            sections.append(f"{summary_data['summary_text']}\n")

        if summary_data and summary_data.get("action_items"):
            sections.append("## ✅ 액션 아이템\n")
            for item in summary_data["action_items"]:
                task = item.get("task", str(item))
                assignee = item.get("assignee")
                deadline = item.get("deadline")
                line = f"- [ ] {task}"
                if assignee:
                    line += f" — @{assignee}"
                if deadline:
                    line += f" ({deadline})"
                sections.append(line)
            sections.append("")

        if summary_data and summary_data.get("key_decisions"):
            sections.append("## 📌 주요 결정\n")
            for decision in summary_data["key_decisions"]:
                sections.append(f"- {decision}")
            sections.append("")

        if summary_data and summary_data.get("next_steps"):
            sections.append("## ➡️ 다음 단계\n")
            for step in summary_data["next_steps"]:
                sections.append(f"- {step}")
            sections.append("")

        if study_pack_data:
            study_pack_md = self._build_study_pack_md(study_pack_data)
            if study_pack_md:
                sections.append("## 🎓 학습팩\n")
                sections.append(study_pack_md)
                sections.append("")

        translation_md = self._build_translation_md(summary_data, minutes_data)
        if translation_md:
            sections.append("## 🌐 번역\n")
            sections.append(translation_md)
            sections.append("")

        if mind_map_data:
            mind_map_md = self._build_mind_map_md(mind_map_data)
            if mind_map_md:
                sections.append("## 🧠 마인드맵\n")
                sections.append(mind_map_md)
                sections.append("")

        if sales_brief_data:
            sales_brief_md = self._build_sales_brief_md(sales_brief_data)
            if sales_brief_md:
                sections.append("## 💼 영업 브리프\n")
                sections.append(sales_brief_md)
                sections.append("")

        if minutes_data:
            transcript_md = self._build_transcript_md(minutes_data)
            if transcript_md:
                sections.append("## 📝 회의록\n")
                sections.append(transcript_md)
                sections.append("")

        if sentiment_data:
            sentiment_md = self._build_sentiment_md(sentiment_data)
            if sentiment_md:
                sections.append("## 📊 감정 분석\n")
                sections.append(sentiment_md)
                sections.append("")

        if tone_data:
            tone_md = self._build_tone_md(tone_data)
            if tone_md:
                sections.append("## 🎵 톤 분석\n")
                sections.append(tone_md)
                sections.append("")

        created_at = meeting_data.get("created_at", "")
        dt = self._parse_datetime(created_at)
        date_link = dt.strftime("%Y-%m-%d") if dt else "Index"
        sections.append("## 🔗 링크\n")
        sections.append(f"[[{date_link}]] | [[Meetings]] | [[Voice-to-TextNote]]\n")

        return "\n".join(sections)

    def _build_mind_map_md(self, mind_map_data: dict[str, Any]) -> str:
        root = mind_map_data.get("root")
        if not isinstance(root, dict):
            return ""
        lines: list[str] = []

        def append_node(node: dict[str, Any], depth: int = 0) -> None:
            title = str(node.get("title", "")).strip()
            summary = str(node.get("summary", "")).strip()
            if title:
                indent = "  " * depth
                suffix = f": {summary}" if summary else ""
                lines.append(f"{indent}- **{title}**{suffix}")
            children = node.get("children") or []
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        append_node(child, depth + 1)

        append_node(root)

        edges = mind_map_data.get("edges") or []
        if isinstance(edges, list) and edges:
            lines.append("")
            lines.append("### 관계")
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                source = str(edge.get("source", "")).strip()
                target = str(edge.get("target", "")).strip()
                relation = str(edge.get("relation", "")).strip()
                if source or target or relation:
                    lines.append(f"- `{source}` → `{target}`: {relation}")

        return "\n".join(lines).strip()

    def _build_sales_brief_md(self, sales_brief_data: dict[str, Any]) -> str:
        lines: list[str] = []
        crm = sales_brief_data.get("crm")
        if isinstance(crm, dict):
            company = str(crm.get("company", "")).strip()
            contact_name = str(crm.get("contact_name", "")).strip()
            if company or contact_name:
                lines.append(f"- 고객: {company or '미지정'} / {contact_name or '미지정'}")
                lines.append("")

        next_steps = sales_brief_data.get("next_steps") or []
        if isinstance(next_steps, list) and next_steps:
            lines.append("### 다음 영업 단계")
            for step in next_steps:
                lines.append(f"- {step}")
            lines.append("")

        follow_up_message = str(sales_brief_data.get("follow_up_message", "")).strip()
        if follow_up_message:
            lines.append("### 후속 메시지")
            lines.append(follow_up_message)

        return "\n".join(lines).strip()

    def _build_study_pack_md(self, study_pack_data: dict[str, Any]) -> str:
        lines: list[str] = []

        mode = study_pack_data.get("mode")
        if mode:
            lines.append(f"- 모드: `{mode}`")
            lines.append("")

        study_notes = str(study_pack_data.get("study_notes", "")).strip()
        if study_notes:
            lines.append("### 학습 노트")
            lines.append(study_notes)
            lines.append("")

        key_concepts = study_pack_data.get("key_concepts") or []
        if key_concepts:
            lines.append("### 핵심 개념")
            for item in key_concepts:
                if not isinstance(item, dict):
                    continue
                term = str(item.get("term", "")).strip()
                explanation = str(item.get("explanation", "")).strip()
                if term and explanation:
                    lines.append(f"- **{term}**: {explanation}")
                elif term:
                    lines.append(f"- **{term}**")
            lines.append("")

        flashcards = study_pack_data.get("flashcards") or []
        if flashcards:
            lines.append("### 플래시카드")
            for index, item in enumerate(flashcards, start=1):
                if not isinstance(item, dict):
                    continue
                front = str(item.get("front", "")).strip()
                back = str(item.get("back", "")).strip()
                if front or back:
                    lines.append(f"{index}. **Q.** {front}")
                    lines.append(f"   - **A.** {back}")
            lines.append("")

        quiz_questions = study_pack_data.get("quiz_questions") or []
        if quiz_questions:
            lines.append("### 복습 퀴즈")
            for index, item in enumerate(quiz_questions, start=1):
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question", "")).strip()
                answer = str(item.get("answer", "")).strip()
                difficulty = str(item.get("difficulty", "")).strip()
                suffix = f" ({difficulty})" if difficulty else ""
                if question or answer:
                    lines.append(f"{index}. {question}{suffix}")
                    lines.append(f"   - 정답: {answer}")

        return "\n".join(line for line in lines if line is not None).strip()

    def _build_translation_md(
        self,
        summary_data: dict[str, Any] | None,
        minutes_data: dict[str, Any] | None,
    ) -> str:
        lines: list[str] = []
        seen: set[tuple[str, str, str]] = set()

        for fallback_source, data in (("summary", summary_data), ("minutes", minutes_data)):
            if not data:
                continue
            translations = data.get("translations")
            if not isinstance(translations, dict):
                continue
            for payload in translations.values():
                if not isinstance(payload, dict):
                    continue
                translated_text = str(payload.get("translated_text", "")).strip()
                if not translated_text:
                    continue
                source_type = str(payload.get("source_type") or fallback_source)
                target_language = str(payload.get("target_language") or "").strip()
                key = (source_type, target_language, translated_text)
                if key in seen:
                    continue
                seen.add(key)
                language_label = target_language or "unknown"
                source_label = "요약" if source_type == "summary" else "회의록"
                lines.append(f"### {language_label} ({source_label})")
                lines.append(translated_text)
                lines.append("")

        return "\n".join(lines).strip()

    def _build_transcript_md(self, minutes_data: dict[str, Any]) -> str:
        segments = minutes_data.get("segments") or []
        if not segments:
            return ""
        lines: list[str] = []
        for seg in segments:
            start = seg.get("start", 0)
            speaker = seg.get("speaker_name") or seg.get("speaker_id") or "Speaker"
            text = seg.get("text", "")
            time_str = self._seconds_to_hhmmss(float(start))
            lines.append(f"**[{time_str}] {speaker}**: {text}")
        return "\n".join(lines)

    def _build_sentiment_md(self, sentiment_data: dict[str, Any]) -> str:
        overall = sentiment_data.get("overall_sentiment", "neutral")
        emotion = sentiment_data.get("overall_emotion", "neutral")
        lines = [f"- 전체 감정: {overall} ({emotion})"]

        speakers = sentiment_data.get("speakers") or []
        if speakers:
            lines.append("")
            lines.append("### 화자별 감정")
            for sp in speakers:
                name = sp.get("speaker", "Unknown")
                dominant = sp.get("dominant_emotion", "neutral")
                pos = sp.get("positive_ratio", 0)
                neu = sp.get("neutral_ratio", 0)
                neg = sp.get("negative_ratio", 0)
                lines.append(
                    f"- **{name}**: {dominant} (긍정 {pos:.0%} / 중립 {neu:.0%} / 부정 {neg:.0%})"
                )
        return "\n".join(lines)

    def _build_tone_md(self, tone_data: dict[str, Any]) -> str:
        overall = tone_data.get("overall_tone", "unknown")
        lines = [f"- 전체 톤: {overall}"]

        speakers = tone_data.get("speakers") or []
        if speakers:
            lines.append("")
            lines.append("### 화자별 톤")
            for sp in speakers:
                name = sp.get("speaker", "Unknown")
                dominant = sp.get("dominant_tone", "unknown")
                avg_pitch = sp.get("avg_pitch", 0)
                lines.append(f"- **{name}**: {dominant} (평균 피치 {avg_pitch:.0f}Hz)")
        return "\n".join(lines)

    def _seconds_to_hhmmss(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def atomic_write(self, file_path: Path, content: str, exist_ok: bool = True) -> bool:
        """REQ-OBS-008: atomic write (temp → fsync → link/replace).

        exist_ok=True: os.replace (overwrite always)
        exist_ok=False: os.link (atomic create-only, raises FileExistsError if exists)
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=str(file_path.parent), prefix=".obs_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            if exist_ok:
                os.replace(tmp_path, file_path)
                return True
            else:
                try:
                    os.link(tmp_path, file_path)
                    return True
                except FileExistsError:
                    return False
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def build_obsidian_uri(self, vault_path: str, file_path: Path) -> str:
        """REQ-OBS-009: obsidian:// URI 생성."""
        vault = Path(vault_path).expanduser().resolve()
        vault_name = vault.name

        rel = file_path.resolve().relative_to(vault)
        rel_str = str(rel)
        if rel_str.endswith(".md"):
            rel_str = rel_str[:-3]

        encoded = quote(rel_str, safe="")
        return f"obsidian://open?vault={quote(vault_name)}&file={encoded}"

    def compose_note(
        self,
        meeting_data: dict[str, Any],
        minutes_data: dict[str, Any] | None,
        summary_data: dict[str, Any] | None,
        sentiment_data: dict[str, Any] | None,
        tone_data: dict[str, Any] | None,
        study_pack_data: dict[str, Any] | None = None,
        mind_map_data: dict[str, Any] | None = None,
        sales_brief_data: dict[str, Any] | None = None,
        frontmatter_custom: dict[str, Any] | None = None,
    ) -> str:
        frontmatter = self.build_frontmatter(
            meeting_data,
            minutes_data,
            summary_data,
            sentiment_data,
            tone_data,
            custom=frontmatter_custom,
        )
        body = self.build_note_body(
            meeting_data,
            minutes_data,
            summary_data,
            sentiment_data,
            tone_data,
            study_pack_data,
            mind_map_data,
            sales_brief_data,
        )
        return f"{frontmatter}\n\n{body}"


obsidian_service = ObsidianService()
