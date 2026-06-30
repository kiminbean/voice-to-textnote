"""Study Pack schemas for transcript-based learning artifacts."""

from enum import StrEnum

from pydantic import BaseModel, Field


class StudyPackMode(StrEnum):
    """Learning artifact mode."""

    GENERAL = "general"
    LECTURE = "lecture"
    MEETING = "meeting"
    INTERVIEW = "interview"
    SERMON = "sermon"


class StudyPackCreateRequest(BaseModel):
    """Study pack generation request."""

    mode: StudyPackMode = Field(default=StudyPackMode.GENERAL, description="Study pack mode")
    language: str = Field(default="ko", min_length=2, max_length=16, description="Output language")
    max_tokens: int = Field(
        default=1800,
        ge=512,
        le=4096,
        description="ZAI-compatible API max response tokens",
    )
    force_refresh: bool = Field(default=False, description="Regenerate even when cached")


class StudySourceRef(BaseModel):
    """Source transcript reference."""

    segment_index: int = Field(ge=0, description="Transcript segment index")
    speaker: str | None = Field(default=None, description="Speaker label")
    start: float | None = Field(default=None, ge=0.0, description="Segment start seconds")
    end: float | None = Field(default=None, ge=0.0, description="Segment end seconds")
    text: str = Field(default="", description="Source text excerpt")


class StudyKeyConcept(BaseModel):
    """Key concept extracted from a transcript."""

    term: str = Field(..., min_length=1, description="Concept term")
    explanation: str = Field(..., min_length=1, description="Grounded explanation")
    source_refs: list[int] = Field(default_factory=list, description="Segment indexes")


class StudyFlashcard(BaseModel):
    """Flashcard item."""

    front: str = Field(..., min_length=1, description="Prompt side")
    back: str = Field(..., min_length=1, description="Answer side")
    source_refs: list[int] = Field(default_factory=list, description="Segment indexes")


class StudyQuizQuestion(BaseModel):
    """Quiz question item."""

    question: str = Field(..., min_length=1, description="Quiz question")
    answer: str = Field(..., min_length=1, description="Correct answer")
    difficulty: str = Field(default="medium", description="easy/medium/hard")
    source_refs: list[int] = Field(default_factory=list, description="Segment indexes")


class StudyPackResponse(BaseModel):
    """Generated study pack response."""

    task_id: str = Field(..., min_length=1, description="Source minutes task ID")
    mode: StudyPackMode = Field(default=StudyPackMode.GENERAL)
    language: str = Field(default="ko")
    key_concepts: list[StudyKeyConcept] = Field(default_factory=list)
    flashcards: list[StudyFlashcard] = Field(default_factory=list)
    quiz_questions: list[StudyQuizQuestion] = Field(default_factory=list)
    study_notes: str = Field(default="")
    source_refs: list[StudySourceRef] = Field(default_factory=list)
    created_at: str = Field(..., description="ISO-8601 creation timestamp")
