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
import hashlib
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from functools import wraps
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Column, String, Integer, Float, Text, Date, DateTime,
    CheckConstraint, UniqueConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import UUID
from open_webui.internal.cogniforce_db import CogniforceBase, get_cogniforce_db
from open_webui.internal.db import JSONField, get_db

# Import simplified OpenTelemetry integration
from .analytics_otel import track_analytics_operation, track_cache_operation, DatabaseOperationTracker, log_analytics_event
from .analytics_cache import cached, get_analytics_cache

# Configure structured logger for analytics
log = logging.getLogger(__name__)


def log_performance(operation_name: str):
    """Decorator to log performance metrics for analytics operations."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = str(uuid.uuid4())[:8]

            log.info(
                "Starting analytics operation",
                extra={
                    "operation_name": operation_name,
                    "operation_id": operation_id,
                    "timestamp": datetime.now().isoformat()
                }
            )

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                log.info(
                    "Analytics operation completed successfully",
                    extra={
                        "operation_name": operation_name,
                        "operation_id": operation_id,
                        "duration_seconds": round(duration, 3),
                        "result_count": len(result) if isinstance(result, list) else 1,
                        "timestamp": datetime.now().isoformat()
                    }
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                log.error(
                    "Analytics operation failed",
                    extra={
                        "operation_name": operation_name,
                        "operation_id": operation_id,
                        "duration_seconds": round(duration, 3),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "timestamp": datetime.now().isoformat()
                    },
                    exc_info=True
                )

                raise

        return wrapper
    return decorator


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
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now())
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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now())
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now())

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

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now())

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


####################
# Response Models (from router)
####################

class AnalyticsSummary(BaseModel):
    total_conversations: int = Field(alias="totalConversations")
    total_time_saved: int = Field(alias="totalTimeSaved")  # minutes
    avg_time_saved_per_conversation: float = Field(alias="avgTimeSavedPerConversation")
    confidence_level: float = Field(alias="confidenceLevel")

    class Config:
        populate_by_name = True


class DailyTrendItem(BaseModel):
    date: str
    conversations: int
    time_saved: int = Field(alias="timeSaved")  # minutes
    avg_confidence: float = Field(alias="avgConfidence")

    class Config:
        populate_by_name = True


class UserBreakdownItem(BaseModel):
    user_id_hash: str = Field(alias="userIdHash")
    user_name: str = Field(alias="userName")
    conversations: int
    time_saved: int = Field(alias="timeSaved")  # minutes
    avg_confidence: float = Field(alias="avgConfidence")

    class Config:
        populate_by_name = True


class ConversationItem(BaseModel):
    id: str
    user_name: str = Field(alias="userName")
    created_at: str = Field(alias="createdAt")
    time_saved: int = Field(alias="timeSaved")  # minutes
    confidence: int
    summary: str

    class Config:
        populate_by_name = True


class HealthStatus(BaseModel):
    status: str
    last_processing_run: Optional[str] = Field(alias="lastProcessingRun")
    next_scheduled_run: str = Field(alias="nextScheduledRun")
    system_info: Dict[str, Any] = Field(alias="systemInfo")

    class Config:
        populate_by_name = True


####################
# Analytics Table Class
####################

class AnalyticsTable:
    """Analytics data access layer following OpenWebUI Table class pattern."""

    def _get_user_name_from_hash(self, user_hash: str) -> str:
        """Map user hash back to real name and email for display."""
        try:
            log.debug(
                "Looking up user name from hash",
                extra={
                    "user_hash_prefix": user_hash[:8],
                    "timestamp": datetime.now().isoformat()
                }
            )

            # Get all users from OpenWebUI database and find matching hash
            with get_db() as db:
                result = db.execute(text('SELECT id, email, name FROM "user"'))
                users = result.fetchall()

                for user in users:
                    user_email = user[1]  # email column
                    user_name = user[2]   # name column

                    # Generate hash for this user's email
                    email_hash = hashlib.sha256(user_email.encode()).hexdigest()

                    if email_hash == user_hash:
                        # Return format: "Name (email)"
                        log.debug(
                            "User name resolved successfully",
                            extra={
                                "user_hash_prefix": user_hash[:8],
                                "user_name": user_name,
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                        return f"{user_name} ({user_email})"

                # Fallback for unknown hashes
                log.warning(
                    "User hash not found in database",
                    extra={
                        "user_hash_prefix": user_hash[:8],
                        "total_users_checked": len(users),
                        "timestamp": datetime.now().isoformat()
                    }
                )
                return f"User {user_hash[:8]}"

        except Exception as e:
            # Fallback in case of database error
            log.error(
                "Database error during user lookup",
                extra={
                    "user_hash_prefix": user_hash[:8],
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                exc_info=True
            )
            return f"User {user_hash[:8]}"

    @track_analytics_operation("get_summary_data")
    @cached(ttl=300, key_prefix="analytics")  # Cache for 5 minutes
    def get_summary_data(self) -> AnalyticsSummary:
        """Get analytics summary from database."""
        with get_cogniforce_db() as db:
            # Query conversation analysis table for aggregated metrics
            result = db.execute(text("""
                SELECT
                    COUNT(*) as total_conversations,
                    COALESCE(SUM(time_saved_minutes), 0) as total_time_saved,
                    COALESCE(AVG(time_saved_minutes), 0) as avg_time_saved,
                    COALESCE(AVG(confidence_level), 0) as avg_confidence
                FROM conversation_analysis
            """))

            row = result.fetchone()
            if row:
                return AnalyticsSummary(
                    total_conversations=row[0] or 0,
                    total_time_saved=row[1] or 0,
                    avg_time_saved_per_conversation=float(row[2] or 0),
                    confidence_level=float(row[3] or 0)
                )

            # Return empty data if no analysis exists
            return AnalyticsSummary(
                total_conversations=0,
                total_time_saved=0,
                avg_time_saved_per_conversation=0.0,
                confidence_level=0.0
            )

    @track_analytics_operation("get_daily_trend_data")
    @cached(ttl=180, key_prefix="analytics")  # Cache for 3 minutes
    def get_daily_trend_data(self, days: int) -> List[DailyTrendItem]:
        """Get daily trend data from database."""
        with get_cogniforce_db() as db:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days-1)

            result = db.execute(text("""
                SELECT
                    analysis_date,
                    COALESCE(SUM(conversation_count), 0) as conversations,
                    COALESCE(SUM(total_time_saved), 0) as time_saved,
                    COALESCE(AVG(avg_confidence_level), 0) as avg_confidence
                FROM daily_aggregates
                WHERE analysis_date >= :start_date AND analysis_date <= :end_date
                AND user_id_hash IS NULL  -- Global aggregates only
                GROUP BY analysis_date
                ORDER BY analysis_date DESC
            """), {"start_date": start_date, "end_date": end_date})

            trend_data = []
            for row in result.fetchall():
                trend_data.append(DailyTrendItem(
                    date=row[0].isoformat(),
                    conversations=row[1] or 0,
                    time_saved=row[2] or 0,
                    avg_confidence=float(row[3] or 0)
                ))

            return trend_data

    @track_analytics_operation("get_user_breakdown_data")
    @cached(ttl=240, key_prefix="analytics")  # Cache for 4 minutes
    def get_user_breakdown_data(self, limit: int) -> List[UserBreakdownItem]:
        """Get user breakdown data from database."""
        with get_cogniforce_db() as db:
            result = db.execute(text("""
                SELECT
                    user_id_hash,
                    SUM(conversation_count) as conversations,
                    SUM(total_time_saved) as time_saved,
                    AVG(avg_confidence_level) as avg_confidence
                FROM daily_aggregates
                WHERE user_id_hash IS NOT NULL
                GROUP BY user_id_hash
                ORDER BY SUM(total_time_saved) DESC
                LIMIT :limit
            """), {"limit": limit})

            users = []
            for row in result.fetchall():
                users.append(UserBreakdownItem(
                    user_id_hash=row[0],
                    user_name=self._get_user_name_from_hash(row[0]),  # Real user name
                    conversations=row[1] or 0,
                    time_saved=row[2] or 0,
                    avg_confidence=float(row[3] or 0)
                ))

            return users

    @track_analytics_operation("get_conversations_data")
    @cached(ttl=120, key_prefix="analytics")  # Cache for 2 minutes
    def get_conversations_data(self, limit: int, offset: int) -> List[ConversationItem]:
        """Get recent conversations with analytics data."""
        with get_cogniforce_db() as db:
            result = db.execute(text("""
                SELECT
                    conversation_id,
                    user_id_hash,
                    first_message_at,
                    time_saved_minutes,
                    confidence_level,
                    COALESCE(conversation_summary, 'No summary available') as summary
                FROM conversation_analysis
                ORDER BY processed_at DESC
                LIMIT :limit OFFSET :offset
            """), {"limit": limit, "offset": offset})

            conversations = []
            for row in result.fetchall():
                conversations.append(ConversationItem(
                    id=row[0],
                    user_name=self._get_user_name_from_hash(row[1]),  # Real user name
                    created_at=row[2].isoformat() if row[2] else datetime.now().isoformat(),
                    time_saved=row[3] or 0,
                    confidence=row[4] or 0,
                    summary=row[5] or "No summary available"
                ))

            return conversations

    @track_analytics_operation("get_health_status_data")
    @cached(ttl=60, key_prefix="analytics")  # Cache for 1 minute
    def get_health_status_data(self) -> HealthStatus:
        """Get system health status from database."""
        with get_cogniforce_db() as db:
            # Get latest processing run
            result = db.execute(text("""
                SELECT
                    run_date,
                    started_at,
                    completed_at,
                    status,
                    conversations_processed,
                    conversations_failed
                FROM processing_log
                ORDER BY started_at DESC
                LIMIT 1
            """))

            row = result.fetchone()
            if row:
                last_run = row[2].isoformat() if row[2] else None
                status = "healthy" if row[3] == "completed" else "warning"
            else:
                last_run = None
                status = "no_data"

            # Next scheduled run (assuming daily processing)
            next_run = (datetime.now().replace(hour=23, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()

            return HealthStatus(
                status=status,
                last_processing_run=last_run,
                next_scheduled_run=next_run,
                system_info={
                    "timezone": "UTC",
                    "idle_threshold_minutes": 10,
                    "processing_version": "1.0",
                    "database_status": "connected",
                    "llm_integration": "ready"
                }
            )


# Global instance following OpenWebUI pattern
Analytics = AnalyticsTable()