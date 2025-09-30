"""
Analytics Tables for Cogniforce Database

This module contains SQLAlchemy models for the analytics tables:
- chat_analysis: Per-chat analysis results
- daily_aggregates: Pre-computed daily statistics
- processing_log: Processing runs and system health tracking

These tables are created in the cogniforce database alongside the existing
conversation_insights and user_engagement tables.
"""

import math
import time
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from functools import wraps
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Column, String, Integer, Float, Text, Date, DateTime,
    CheckConstraint, UniqueConstraint, Index, func, cast
)
from sqlalchemy.dialects.postgresql import UUID
from open_webui.internal.cogniforce_db import CogniforceBase, get_cogniforce_db
from open_webui.internal.db import JSONField, get_db
from open_webui.models.users import User

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

class ChatAnalysis(CogniforceBase):
    """Stores per-chat analysis results for time savings analytics."""
    __tablename__ = "chat_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source chat identification
    chat_id = Column(String(255), nullable=False, unique=True)
    user_id = Column(String(255), nullable=False)  # OpenWebUI user ID

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
    chat_date = Column(Date, nullable=False)  # Date when chat actually occurred (from created_at)
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now())
    processing_version = Column(String(20), default="1.0")

    # Analysis data
    chat_summary = Column(Text, nullable=True)  # Redacted summary sent to LLM
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
        Index('idx_chat_analysis_user_date', 'user_id', 'processed_at'),
        Index('idx_chat_analysis_processed_at', 'processed_at'),
    )


class DailyAggregate(CogniforceBase):
    """Pre-computed daily statistics for dashboard performance."""
    __tablename__ = "daily_aggregates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Aggregation period
    analysis_date = Column(Date, nullable=False)
    user_id = Column(String(255), nullable=True)  # NULL for global aggregates

    # Counts
    chat_count = Column(Integer, nullable=False, default=0)
    message_count = Column(Integer, nullable=False, default=0)

    # Time metrics (in minutes)
    total_active_time = Column(Integer, nullable=False, default=0)
    total_manual_time_estimated = Column(Integer, nullable=False, default=0)
    total_time_saved = Column(Integer, nullable=False, default=0)
    avg_time_saved_per_chat = Column(Float, nullable=True)

    # Confidence metrics
    avg_confidence_level = Column(Float, nullable=True)

    # Processing metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now())
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now())

    __table_args__ = (
        UniqueConstraint('analysis_date', 'user_id', name='unique_daily_aggregate'),
        CheckConstraint(
            'chat_count >= 0 AND '
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
    target_date = Column(Date, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default='running')  # running, completed, failed

    # Processing statistics
    chats_processed = Column(Integer, default=0)
    chats_skipped = Column(Integer, default=0)
    chats_failed = Column(Integer, default=0)

    # Performance metrics
    total_llm_requests = Column(Integer, default=0)
    total_llm_cost_usd = Column(Float, default=0.0)
    processing_duration_seconds = Column(Integer, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONField, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now())

    __table_args__ = (
        Index('idx_processing_log_target_date', 'target_date'),
        CheckConstraint(
            'chats_processed >= 0 AND '
            'chats_skipped >= 0 AND '
            'chats_failed >= 0',
            name='positive_processing_counts'
        ),
    )


####################
# Pydantic Models
####################

class ChatAnalysisModel(BaseModel):
    """Pydantic model for chat analysis data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: str
    user_id: str
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
    chat_summary: Optional[str] = None
    llm_response: Optional[dict] = None


class DailyAggregateModel(BaseModel):
    """Pydantic model for daily aggregate data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    analysis_date: str     # ISO date string
    user_id: Optional[str] = None
    chat_count: int
    message_count: int
    total_active_time: int
    total_manual_time_estimated: int
    total_time_saved: int
    avg_time_saved_per_chat: Optional[float] = None
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
    chats_processed: int
    chats_skipped: int
    chats_failed: int
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
    total_chats: int
    total_time_saved: int
    avg_time_saved_per_chat: float
    avg_confidence_level: float
    date_range: str


class UserBreakdownModel(BaseModel):
    """Per-user analytics breakdown."""
    user_id: str
    chat_count: int
    total_time_saved: int
    avg_time_saved_per_chat: float
    avg_confidence_level: float


####################
# Response Models (from router)
####################

class AnalyticsSummary(BaseModel):
    total_chats: int = Field(alias="totalChats")
    total_time_saved: int = Field(alias="totalTimeSaved")  # minutes
    avg_time_saved_per_chat: float = Field(alias="avgTimeSavedPerChat")
    confidence_level: float = Field(alias="confidenceLevel")

    class Config:
        populate_by_name = True


class DailyTrendItem(BaseModel):
    date: str = Field(alias="date")
    chats: int = Field(alias="chats")
    time_saved: int = Field(alias="timeSaved")  # minutes
    avg_confidence: float = Field(alias="avgConfidence")

    class Config:
        populate_by_name = True


class UserBreakdownItem(BaseModel):
    user_name: str = Field(alias="userName")
    chats: int = Field(alias="chats")
    time_saved: int = Field(alias="timeSaved")  # minutes
    avg_confidence: float = Field(alias="avgConfidence")

    class Config:
        populate_by_name = True


class ChatItem(BaseModel):
    id: str = Field(alias="id")
    user_name: str = Field(alias="userName")
    created_at: str = Field(alias="createdAt")
    time_saved: int = Field(alias="timeSaved")  # minutes
    confidence: int = Field(alias="confidence")
    topic: str = Field(alias="topic")
    message_count: int = Field(alias="messageCount")
    user_message_count: int = Field(alias="userMessageCount")
    assistant_message_count: int = Field(alias="assistantMessageCount")
    summary: Optional[str] = Field(default=None, alias="summary")  # Only included if full_summary=True

    class Config:
        populate_by_name = True


class SystemInfo(BaseModel):
    timezone: str = Field(alias="timezone")
    idle_threshold_minutes: int = Field(alias="idleThresholdMinutes")
    processing_version: str = Field(alias="processingVersion")
    database_status: str = Field(alias="databaseStatus")
    llm_integration: str = Field(alias="llmIntegration")

    class Config:
        populate_by_name = True


class HealthStatus(BaseModel):
    status: str = Field(alias="status")
    last_processing_run: Optional[str] = Field(alias="lastProcessingRun")
    next_scheduled_run: str = Field(alias="nextScheduledRun")
    system_info: SystemInfo = Field(alias="systemInfo")

    class Config:
        populate_by_name = True


class ProcessingTriggerResponse(BaseModel):
    status: str = Field(alias="status")
    target_date: str = Field(alias="targetDate")
    message: str = Field(alias="message")
    processing_log_id: Optional[str] = Field(alias="processingLogId")
    chats_processed: int = Field(alias="chatsProcessed")
    chats_failed: int = Field(alias="chatsFailed")
    duration_seconds: float = Field(alias="durationSeconds")
    total_cost_usd: float = Field(alias="totalCostUsd")
    model_used: str = Field(alias="modelUsed")

    class Config:
        populate_by_name = True


class ChatAnalysisResult(BaseModel):
    analysis_id: str = Field(alias="analysisId")
    chat_id: str = Field(alias="chatId")
    chat_date: date = Field(alias="chatDate")
    user_id: str = Field(alias="userId")
    time_saved_minutes: int = Field(alias="timeSavedMinutes")
    active_duration_minutes: int = Field(alias="activeDurationMinutes")
    manual_time_most_likely: int = Field(alias="manualTimeMostLikely")
    message_count: int = Field(alias="messageCount")
    confidence_level: int = Field(alias="confidenceLevel")
    llm_cost: float = Field(alias="llmCost")

    class Config:
        populate_by_name = True


class TimeMetrics(BaseModel):
    first_message_at: datetime = Field(alias="firstMessageAt")
    last_message_at: datetime = Field(alias="lastMessageAt")
    total_duration_minutes: int = Field(alias="totalDurationMinutes")
    active_duration_minutes: int = Field(alias="activeDurationMinutes")
    idle_time_minutes: int = Field(alias="idleTimeMinutes")

    class Config:
        populate_by_name = True


class TimeEstimates(BaseModel):
    low: int = Field(alias="low")
    most_likely: int = Field(alias="mostLikely")
    high: int = Field(alias="high")
    confidence: int = Field(alias="confidence")

    class Config:
        populate_by_name = True


class ProcessingLogResult(BaseModel):
    processing_log_id: str = Field(alias="processingLogId")
    status: str = Field(alias="status")
    duration_seconds: float = Field(alias="durationSeconds")
    chats_processed: int = Field(alias="chatsProcessed")
    chats_failed: int = Field(alias="chatsFailed")
    total_cost_usd: float = Field(alias="totalCostUsd")

    class Config:
        populate_by_name = True


####################
# Analytics Table Class
####################

class AnalyticsTable:
    """Analytics data access layer following OpenWebUI Table class pattern."""

    def _parse_chat_summary(self, raw_summary: str) -> Dict[str, Any]:
        """
        Parse structured chat summary into separate fields.

        Expected format:
        "Chat Analysis Summary:

        Topic: ⚖️ Nixon Ruling and Impeachments
        Message Count: 10
        User Messages: 5
        Assistant Messages: 5

        Content Overview:
        [actual summary text...]"

        Returns:
            Dict with topic, message_count, user_message_count, assistant_message_count, content_summary
        """
        try:
            lines = raw_summary.split('\n')

            # Extract structured data with defaults
            topic = "Untitled Chat"
            message_count = 0
            user_message_count = 0
            assistant_message_count = 0
            content_summary = None

            # Find the content overview section
            content_start_idx = None
            for i, line in enumerate(lines):
                line = line.strip()

                if line.startswith("Topic:"):
                    topic = line.replace("Topic:", "").strip()
                elif line.startswith("Message Count:"):
                    try:
                        message_count = int(line.replace("Message Count:", "").strip())
                    except ValueError:
                        pass
                elif line.startswith("User Messages:"):
                    try:
                        user_message_count = int(line.replace("User Messages:", "").strip())
                    except ValueError:
                        pass
                elif line.startswith("Assistant Messages:"):
                    try:
                        assistant_message_count = int(line.replace("Assistant Messages:", "").strip())
                    except ValueError:
                        pass
                elif line.startswith("Content Overview:"):
                    content_start_idx = i + 1
                    break

            # Extract content summary if found
            if content_start_idx is not None and content_start_idx < len(lines):
                # Join all remaining lines after "Content Overview:"
                content_lines = lines[content_start_idx:]
                content_summary = '\n'.join(content_lines).strip()

            return {
                'topic': topic,
                'message_count': message_count,
                'user_message_count': user_message_count,
                'assistant_message_count': assistant_message_count,
                'content_summary': content_summary
            }

        except Exception as e:
            log.warning(f"Failed to parse chat summary: {e}")
            return {
                'topic': "Parsing Error",
                'message_count': 0,
                'user_message_count': 0,
                'assistant_message_count': 0,
                'content_summary': raw_summary[:200] + "..." if len(raw_summary) > 200 else raw_summary
            }

    def _get_user_name_from_id(self, user_id: str) -> str:
        """Get real user name and email for display using user ID."""
        try:
            log.debug(
                "🔍 Looking up user name from ID",
                extra={
                    "user_id": user_id,
                    "user_id_type": type(user_id).__name__,
                    "timestamp": datetime.now().isoformat()
                }
            )

            # Get user directly from OpenWebUI database using string ID
            with get_db() as db:
                user = db.query(User.id, User.email, User.name).filter(User.id == user_id).first()

                if user:
                    user_id_val, user_email, user_name = user
                    # Return format: "Name (email)"
                    log.debug(
                        "✅ User name resolved successfully",
                        extra={
                            "user_id": user_id,
                            "user_name": user_name,
                            "user_email": user_email,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    return f"{user_name} ({user_email})"
                else:
                    # Fallback for unknown user IDs
                    log.warning(
                        "⚠️ User ID not found in database",
                        extra={
                            "user_id": user_id,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    return f"Unknown User {user_id[:8]}..."

        except Exception as e:
            # Fallback in case of database error
            log.error(
                "💥 Database error during user lookup",
                extra={
                    "user_id": user_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                exc_info=True
            )
            return f"Unknown User {user_id[:8]}..."

    @track_analytics_operation("get_summary_data")
    @cached(ttl=300, key_prefix="analytics")  # Cache for 5 minutes
    def get_summary_data(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> AnalyticsSummary:
        """Get analytics summary from database."""
        with get_cogniforce_db() as db:
            # Build SQLAlchemy ORM query with dynamic date filters
            query = db.query(
                func.count(ChatAnalysis.id).label('total_chats'),
                func.coalesce(func.sum(ChatAnalysis.time_saved_minutes), 0).label('total_time_saved'),
                func.coalesce(func.avg(ChatAnalysis.time_saved_minutes), 0).label('avg_time_saved'),
                func.coalesce(func.avg(ChatAnalysis.confidence_level), 0).label('avg_confidence')
            )

            # Apply date filters if provided (filter by when chat occurred, not when processed)
            if start_date:
                query = query.filter(ChatAnalysis.chat_date >= start_date)

            if end_date:
                query = query.filter(ChatAnalysis.chat_date <= end_date)

            result = query.first()
            if result:
                return AnalyticsSummary(
                    total_chats=result.total_chats or 0,
                    total_time_saved=result.total_time_saved or 0,
                    avg_time_saved_per_chat=float(math.ceil(result.avg_time_saved or 0)),
                    confidence_level=float(math.ceil(result.avg_confidence or 0))
                )

            # Return empty data if no analysis exists
            return AnalyticsSummary(
                total_chats=0,
                total_time_saved=0,
                avg_time_saved_per_chat=0.0,
                confidence_level=0.0
            )

    @track_analytics_operation("get_trends_data")
    @cached(ttl=180, key_prefix="analytics")  # Cache for 3 minutes
    def get_trends_data(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[DailyTrendItem]:
        """Get analytics trend data from database for the specified date range."""
        with get_cogniforce_db() as db:
            # Use provided dates or default to the last 7 days
            if not end_date:
                end_date = datetime.now().date()
            if not start_date:
                start_date = end_date - timedelta(days=6)  # 7 days total including end_date

            # Use SQLAlchemy ORM for aggregated daily trends
            results = db.query(
                DailyAggregate.analysis_date,
                func.coalesce(func.sum(DailyAggregate.chat_count), 0).label('chats'),
                func.coalesce(func.sum(DailyAggregate.total_time_saved), 0).label('time_saved'),
                func.coalesce(func.avg(DailyAggregate.avg_confidence_level), 0).label('avg_confidence')
            ).filter(
                DailyAggregate.analysis_date >= start_date,
                DailyAggregate.analysis_date <= end_date,
                DailyAggregate.user_id.is_(None)  # Global aggregates only
            ).group_by(
                DailyAggregate.analysis_date
            ).order_by(
                DailyAggregate.analysis_date.desc()
            ).all()

            trend_data = []
            for result in results:
                trend_data.append(DailyTrendItem(
                    date=result.analysis_date.isoformat(),
                    chats=result.chats or 0,
                    time_saved=result.time_saved or 0,
                    avg_confidence=float(result.avg_confidence or 0)
                ))

            return trend_data

    @track_analytics_operation("get_user_breakdown_data")
    @cached(ttl=240, key_prefix="analytics")  # Cache for 4 minutes
    def get_user_breakdown_data(self, limit: int, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[UserBreakdownItem]:
        """Get user breakdown data from database."""
        with get_cogniforce_db() as db:
            # Build SQLAlchemy ORM query with dynamic date filters
            query = db.query(
                DailyAggregate.user_id,
                func.sum(DailyAggregate.chat_count).label('chats'),
                func.sum(DailyAggregate.total_time_saved).label('time_saved'),
                func.avg(DailyAggregate.avg_confidence_level).label('avg_confidence')
            ).filter(
                DailyAggregate.user_id.isnot(None)
            )

            # Apply date filters if provided
            if start_date:
                query = query.filter(DailyAggregate.analysis_date >= start_date)

            if end_date:
                query = query.filter(DailyAggregate.analysis_date <= end_date)

            # Group by user and order by total time saved
            results = query.group_by(
                DailyAggregate.user_id
            ).order_by(
                func.sum(DailyAggregate.total_time_saved).desc()
            ).limit(limit).all()

            users = []
            for result in results:
                users.append(UserBreakdownItem(
                    user_name=self._get_user_name_from_id(str(result.user_id)),  # Real user name
                    chats=result.chats or 0,
                    time_saved=result.time_saved or 0,
                    avg_confidence=float(result.avg_confidence or 0)
                ))

            return users

    @track_analytics_operation("get_chats_data")
    @cached(ttl=120, key_prefix="analytics")  # Cache for 2 minutes
    def get_chats_data(self, limit: int, offset: int, full_summary: bool = False, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[ChatItem]:
        """Get recent conversations with analytics data."""
        with get_cogniforce_db() as db:
            # Build SQLAlchemy ORM query with dynamic date filters
            query = db.query(
                ChatAnalysis.chat_id,
                ChatAnalysis.user_id,
                ChatAnalysis.first_message_at,
                ChatAnalysis.time_saved_minutes,
                ChatAnalysis.confidence_level,
                func.coalesce(ChatAnalysis.chat_summary, 'No summary available').label('summary')
            )

            # Apply date filters if provided (filter by when chat occurred, not when processed)
            if start_date:
                query = query.filter(ChatAnalysis.chat_date >= start_date)

            if end_date:
                query = query.filter(ChatAnalysis.chat_date <= end_date)

            # Order by chat date and apply pagination
            results = query.order_by(
                ChatAnalysis.chat_date.desc(),
                ChatAnalysis.first_message_at.desc()
            ).limit(limit).offset(offset).all()

            chats = []
            for result in results:
                # Parse the raw summary into structured data
                raw_summary = result.summary or "No summary available"
                parsed_summary = self._parse_chat_summary(raw_summary)

                chats.append(ChatItem(
                    id=result.chat_id,
                    user_name=self._get_user_name_from_id(str(result.user_id)),  # Real user name
                    created_at=result.first_message_at.isoformat() if result.first_message_at else datetime.now().isoformat(),
                    time_saved=result.time_saved_minutes or 0,
                    confidence=result.confidence_level or 0,
                    topic=parsed_summary['topic'],
                    message_count=parsed_summary['message_count'],
                    user_message_count=parsed_summary['user_message_count'],
                    assistant_message_count=parsed_summary['assistant_message_count'],
                    summary=parsed_summary['content_summary'] if full_summary else "Set query param 'full_summary=true' for complete text."
                ))

            return chats

    @track_analytics_operation("get_health_status_data")
    @cached(ttl=60, key_prefix="analytics")  # Cache for 1 minute
    def get_health_status_data(self) -> HealthStatus:
        """Get system health status from database."""
        with get_cogniforce_db() as db:
            # Get latest processing run using SQLAlchemy ORM
            latest_log = db.query(ProcessingLog).order_by(
                ProcessingLog.started_at.desc()
            ).first()

            if latest_log:
                last_run = latest_log.completed_at.isoformat() if latest_log.completed_at else None
                status = "healthy" if latest_log.status == "completed" else "warning"
            else:
                last_run = None
                status = "no_data"

            # Next scheduled run (assuming daily processing)
            next_run = (datetime.now().replace(hour=23, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()

            return HealthStatus(
                status=status,
                last_processing_run=last_run,
                next_scheduled_run=next_run,
                system_info=SystemInfo(
                    timezone="UTC",
                    idle_threshold_minutes=10,
                    processing_version="1.0",
                    database_status="connected",
                    llm_integration="ready"
                )
            )


# Global instance following OpenWebUI pattern
Analytics = AnalyticsTable()