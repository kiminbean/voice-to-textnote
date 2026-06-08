"""
외부 서비스 통합 관련 데이터베이스 모델
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from backend.app.api.v1.integrations.schemas import IntegrationStatus, IntegrationType

Base = declarative_base()  # type: ignore[misc]


class Integration(Base):  # type: ignore[misc,valid-type]
    """외부 서비스 통합 모델"""
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(String(255), unique=True, index=True, nullable=False)
    integration_type: Any = Column(Enum(*[t.value for t in IntegrationType]), nullable=False)  # type: ignore[var-annotated]
    status: Any = Column(Enum(*[s.value for s in IntegrationStatus]), default=IntegrationStatus.ACTIVE, nullable=False)  # type: ignore[var-annotated]
    user_id = Column(String(255), index=True, nullable=False)
    config = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=True)  # 추가 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_sync_at = Column(DateTime, nullable=True)

    # 관계
    webhook_logs = relationship("WebhookLog", back_populates="integration", cascade="all, delete-orphan")


class WebhookLog(Base):  # type: ignore[misc,valid-type]
    """웹훅 로그 모델"""
    __tablename__ = "webhook_logs"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(String(255), ForeignKey("integrations.integration_id"), nullable=False)
    webhook_type = Column(String(50), nullable=False)  # slack, teams, notion 등
    event_type = Column(String(100), nullable=True)  # meeting.completed, task.updated 등
    request_data = Column(JSON, nullable=True)
    response_data = Column(JSON, nullable=True)
    status = Column(String(20), default="success", nullable=False)  # success, failed, pending
    error_message = Column(Text, nullable=True)
    response_code = Column(Integer, nullable=True)
    processing_time = Column(Integer, nullable=True)  # ms
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 관계
    integration = relationship("Integration", back_populates="webhook_logs")


class SyncHistory(Base):  # type: ignore[misc,valid-type]
    """동기화 이력 모델"""
    __tablename__ = "sync_history"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(String(255), ForeignKey("integrations.integration_id"), nullable=False)
    event_type = Column(String(100), nullable=False)  # meeting.created, meeting.updated 등
    external_id = Column(String(255), nullable=True)  # 외부 서비스의 ID
    sync_status = Column(String(20), default="success", nullable=False)
    data_sent = Column(JSON, nullable=True)
    data_received = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 관계
    integration = relationship("Integration")


class MeetingExport(Base):  # type: ignore[misc,valid-type]
    """회의록 내보내기 모델"""
    __tablename__ = "meeting_exports"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String(255), index=True, nullable=False)
    integration_id = Column(String(255), ForeignKey("integrations.integration_id"), nullable=False)
    export_type = Column(String(50), nullable=False)  # slack, teams, notion
    external_id = Column(String(255), nullable=True)  # 외부 서비스에서 생성된 ID
    status = Column(String(20), default="pending", nullable=False)  # pending, success, failed
    exported_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # 관계
    integration = relationship("Integration")
