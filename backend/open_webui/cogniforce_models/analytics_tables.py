"""
Analytics Tables for Cogniforce Database

This module contains SQLAlchemy models for the analytics tables:
- conversation_analysis: Per-conversation analysis results
- daily_aggregates: Pre-computed daily statistics
- processing_log: Processing runs and system health tracking

These tables are created in the cogniforce database alongside the existing
conversation_insights and user_engagement tables.
"""

import time
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    Column, String, Integer, Float, Text, Date, DateTime,
    CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from open_webui.internal.cogniforce_db import CogniforceBase
from open_webui.internal.db import JSONField


####################
# SQLAlchemy Models
####################

class ConversationAnalysis(CogniforceBase):
    """Stores per-conversation analysis results for time savings analytics."""
    __tablename__ = "conversation_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source conversation identification
    conversation_id = Column(String(255), nullable=False, unique=True)
    user_id_hash = Column(String(64), nullable=False)  # SHA-256 hash for privacy

    # Timing analysis
    first_message_at = Column(DateTime(timezone=True), nullable=False)
    last_message_at = Column(DateTime(timezone=True), nullable=False)
    total_duration_minutes = Column(Integer, nullable=False)
    active_duration_minutes = Column(Integer, nullable=False)  # Excluding idle gaps >10min
    idle_time_minutes = Column(Integer, nullable=False)

    # LLM time estimates (in minutes)
    manual_time_low = Column(Integer, nullable=False)
    manual_time_most_likely = Column(Integer, nullable=False)
    manual_time_high = Column(Integer, nullable=False)
    confidence_level = Column(Integer, nullable=False)  # 0-100

    # Calculated savings
    time_saved_minutes = Column(Integer, nullable=False)  # max(0, manual_most_likely - active_minutes)

    # Metadata
    message_count = Column(Integer, nullable=False)
    processed_at = Column(DateTime(timezone=True), default=lambda: time.time())
    processing_version = Column(String(20), default="1.0")

    # Analysis data
    conversation_summary = Column(Text, nullable=True)  # Redacted summary sent to LLM
    llm_response = Column(JSONField, nullable=True)  # Full LLM response for debugging

    __table_args__ = (
        CheckConstraint(
            'total_duration_minutes >= 0 AND '
            'active_duration_minutes >= 0 AND '
            'idle_time_minutes >= 0 AND '
            'time_saved_minutes >= 0',
            name='positive_durations'
        ),
        CheckConstraint(
            'confidence_level BETWEEN 0 AND 100',
            name='valid_confidence'
        ),
        CheckConstraint(
            'manual_time_low <= manual_time_most_likely AND '
            'manual_time_most_likely <= manual_time_high',
            name='valid_estimates'
        ),
        Index('idx_conversation_analysis_user_date', 'user_id_hash', 'processed_at'),
        Index('idx_conversation_analysis_processed_at', 'processed_at'),
    )


class DailyAggregate(CogniforceBase):
    """Pre-computed daily statistics for dashboard performance."""
    __tablename__ = "daily_aggregates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Aggregation period
    analysis_date = Column(Date, nullable=False)
    user_id_hash = Column(String(64), nullable=True)  # NULL for global aggregates

    # Counts
    conversation_count = Column(Integer, nullable=False, default=0)
    message_count = Column(Integer, nullable=False, default=0)

    # Time metrics (in minutes)
    total_active_time = Column(Integer, nullable=False, default=0)
    total_manual_time_estimated = Column(Integer, nullable=False, default=0)
    total_time_saved = Column(Integer, nullable=False, default=0)
    avg_time_saved_per_conversation = Column(Float, nullable=True)

    # Confidence metrics
    avg_confidence_level = Column(Float, nullable=True)

    # Processing metadata
    created_at = Column(DateTime(timezone=True), default=lambda: time.time())
    updated_at = Column(DateTime(timezone=True), default=lambda: time.time())

    __table_args__ = (
        UniqueConstraint('analysis_date', 'user_id_hash', name='unique_daily_aggregate'),
        CheckConstraint(
            'conversation_count >= 0 AND '
            'message_count >= 0 AND '
            'total_active_time >= 0 AND '
            'total_time_saved >= 0',
            name='positive_aggregates'
        ),
        Index('idx_daily_aggregates_date', 'analysis_date'),
    )


class ProcessingLog(CogniforceBase):
    """Tracks processing runs and system health."""
    __tablename__ = "processing_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Processing run information
    run_date = Column(Date, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default='running')  # running, completed, failed

    # Processing statistics
    conversations_processed = Column(Integer, default=0)
    conversations_skipped = Column(Integer, default=0)
    conversations_failed = Column(Integer, default=0)

    # Performance metrics
    total_llm_requests = Column(Integer, default=0)
    total_llm_cost_usd = Column(Float, default=0.0)
    processing_duration_seconds = Column(Integer, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONField, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: time.time())

    __table_args__ = (
        Index('idx_processing_log_run_date', 'run_date'),
        CheckConstraint(
            'conversations_processed >= 0 AND '
            'conversations_skipped >= 0 AND '
            'conversations_failed >= 0',
            name='positive_processing_counts'
        ),
    )


####################
# Pydantic Models
####################

class ConversationAnalysisModel(BaseModel):
    """Pydantic model for conversation analysis data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: str
    user_id_hash: str
    first_message_at: str  # ISO datetime string
    last_message_at: str   # ISO datetime string
    total_duration_minutes: int
    active_duration_minutes: int
    idle_time_minutes: int
    manual_time_low: int
    manual_time_most_likely: int
    manual_time_high: int
    confidence_level: int
    time_saved_minutes: int
    message_count: int
    processed_at: str      # ISO datetime string
    processing_version: str
    conversation_summary: Optional[str] = None
    llm_response: Optional[dict] = None


class DailyAggregateModel(BaseModel):
    """Pydantic model for daily aggregate data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    analysis_date: str     # ISO date string
    user_id_hash: Optional[str] = None
    conversation_count: int
    message_count: int
    total_active_time: int
    total_manual_time_estimated: int
    total_time_saved: int
    avg_time_saved_per_conversation: Optional[float] = None
    avg_confidence_level: Optional[float] = None
    created_at: str        # ISO datetime string
    updated_at: str        # ISO datetime string


class ProcessingLogModel(BaseModel):
    """Pydantic model for processing log data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_date: str          # ISO date string
    started_at: str        # ISO datetime string
    completed_at: Optional[str] = None  # ISO datetime string
    status: str
    conversations_processed: int
    conversations_skipped: int
    conversations_failed: int
    total_llm_requests: int
    total_llm_cost_usd: float
    processing_duration_seconds: Optional[int] = None
    error_message: Optional[str] = None
    error_details: Optional[dict] = None
    created_at: str        # ISO datetime string


####################
# Analytics Summary Models
####################

class AnalyticsSummaryModel(BaseModel):
    """Summary analytics for dashboard display."""
    total_conversations: int
    total_time_saved: int
    avg_time_saved_per_conversation: float
    avg_confidence_level: float
    date_range: str


class UserBreakdownModel(BaseModel):
    """Per-user analytics breakdown."""
    user_id_hash: str
    conversation_count: int
    total_time_saved: int
    avg_time_saved_per_conversation: float
    avg_confidence_level: float