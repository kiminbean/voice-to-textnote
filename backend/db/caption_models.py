"""
자막 생성 관련 데이터베이스 모델
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()  # type: ignore[misc]


class CaptionSession(Base):  # type: ignore[misc,valid-type]
    """자막 세션 모델"""
    __tablename__ = "caption_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    meeting_id = Column(String(255), index=True, nullable=False)
    user_id = Column(String(255), index=True, nullable=False)
    status: Any = Column(Enum('PENDING', 'PROCESSING', 'ACTIVE', 'COMPLETED', 'FAILED'),  # type: ignore[var-annotated]
                   default='PENDING', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    segments = relationship("CaptionSegment", back_populates="session", cascade="all, delete-orphan")


class CaptionSegment(Base):  # type: ignore[misc,valid-type]
    """자막 세그먼트 모델"""
    __tablename__ = "caption_segments"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("caption_sessions.id"), nullable=False)
    index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    confidence = Column(Float, nullable=False)
    speaker_id = Column(String(255), nullable=True)

    # 관계
    session = relationship("CaptionSession", back_populates="segments")


class CaptionTask(Base):  # type: ignore[misc,valid-type]
    """자막 작업 모델"""
    __tablename__ = "caption_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), unique=True, index=True, nullable=False)
    meeting_id = Column(String(255), index=True, nullable=False)
    user_id = Column(String(255), index=True, nullable=False)
    audio_url = Column(Text, nullable=True)
    language = Column(String(10), default='ko', nullable=False)
    format: Any = Column(Enum('VTT', 'SRT', 'JSON'), default='VTT', nullable=False)  # type: ignore[var-annotated]
    status: Any = Column(Enum('PENDING', 'PROCESSING', 'ACTIVE', 'COMPLETED', 'FAILED'),
                        default='PENDING', nullable=False)  # type: ignore[var-annotated]
    progress = Column(Integer, default=0, nullable=False)  # 0-100
    error_message = Column(Text, nullable=True)
    result_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
