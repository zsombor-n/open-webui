# AI Time Savings Analytics - Backend Implementation Specification

## Executive Summary

This document provides a comprehensive specification for implementing the backend analytics system that powers the AI Time Savings Analytics dashboard. The system analyzes chat conversations to estimate manual time requirements and calculate time savings achieved through AI assistance.

### Goals
- **Daily automated analysis** of conversation efficiency
- **LLM-powered time estimation** for manual task completion
- **Aggregate analytics** with user privacy protection
- **Secure dashboard** with password protection
- **Scalable architecture** supporting future enhancements

---

## Architecture Overview

### System Components

```
┌───────────────┐    ┌─────────────────┐    ┌────────────────┐
│ Scheduler     │───▶│  Data Processor │───▶│  Analytics DB  │
│ (APScheduler) │    │                 │    │  (PostgreSQL)  │
└───────────────┘    └─────────────────┘    └────────────────┘
                               │
                               ▼
                       ┌──────────────────┐
                       │   OpenAI API     │
                       │ (Time Estimates) │
                       └──────────────────┘
                                │
                                ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Analytics API  │───▶│    Dashboard    │
                       │   (FastAPI)     │    │   (Frontend)    │
                       └─────────────────┘    └─────────────────┘
```

### Technology Stack
- **Backend**: Python FastAPI (existing Open WebUI infrastructure)
- **Database**: PostgreSQL (cogniforce database - dual-database setup with openwebui)
- **Scheduler**: APScheduler
- **LLM Integration**: OpenAI API
- **Data Processing**: Pandas, SQLAlchemy
- **Authentication**: Environment-based password protection

---

## Database Schema Design

### Cogniforce Database Tables

These tables are created in the `cogniforce` database alongside the existing `conversation_insights` and `user_engagement` tables from the dual-database setup.

#### 1. `conversation_analysis` Table
Stores per-conversation analysis results.

```sql
CREATE TABLE conversation_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source conversation identification
    conversation_id VARCHAR(255) NOT NULL,
    user_id_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash for privacy

    -- Timing analysis
    first_message_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_message_at TIMESTAMP WITH TIME ZONE NOT NULL,
    total_duration_minutes INTEGER NOT NULL,
    active_duration_minutes INTEGER NOT NULL,  -- Excluding idle gaps >10min
    idle_time_minutes INTEGER NOT NULL,

    -- LLM time estimates (in minutes)
    manual_time_low INTEGER NOT NULL,
    manual_time_most_likely INTEGER NOT NULL,
    manual_time_high INTEGER NOT NULL,
    confidence_level INTEGER NOT NULL,  -- 0-100

    -- Calculated savings
    time_saved_minutes INTEGER NOT NULL,  -- max(0, manual_most_likely - active_minutes)

    -- Metadata
    message_count INTEGER NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processing_version VARCHAR(20) DEFAULT '1.0',

    -- Analysis data
    conversation_summary TEXT,  -- Redacted summary sent to LLM
    llm_response JSONB,  -- Full LLM response for debugging

    CONSTRAINT positive_durations CHECK (
        total_duration_minutes >= 0 AND
        active_duration_minutes >= 0 AND
        idle_time_minutes >= 0 AND
        time_saved_minutes >= 0
    ),
    CONSTRAINT valid_confidence CHECK (confidence_level BETWEEN 0 AND 100),
    CONSTRAINT valid_estimates CHECK (
        manual_time_low <= manual_time_most_likely AND
        manual_time_most_likely <= manual_time_high
    )
);

-- Indexes for performance
CREATE INDEX idx_conversation_analysis_user_date ON conversation_analysis (user_id_hash, DATE(processed_at));
CREATE INDEX idx_conversation_analysis_processed_at ON conversation_analysis (processed_at);
CREATE UNIQUE INDEX idx_conversation_analysis_conversation_id ON conversation_analysis (conversation_id);
```

#### 2. `daily_aggregates` Table
Pre-computed daily statistics for dashboard performance.

```sql
CREATE TABLE daily_aggregates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Aggregation period
    analysis_date DATE NOT NULL,
    user_id_hash VARCHAR(64),  -- NULL for global aggregates

    -- Counts
    conversation_count INTEGER NOT NULL DEFAULT 0,
    message_count INTEGER NOT NULL DEFAULT 0,

    -- Time metrics (in minutes)
    total_active_time INTEGER NOT NULL DEFAULT 0,
    total_manual_time_estimated INTEGER NOT NULL DEFAULT 0,
    total_time_saved INTEGER NOT NULL DEFAULT 0,
    avg_time_saved_per_conversation DECIMAL(10,2),

    -- Confidence metrics
    avg_confidence_level DECIMAL(5,2),

    -- Processing metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT positive_aggregates CHECK (
        conversation_count >= 0 AND
        message_count >= 0 AND
        total_active_time >= 0 AND
        total_time_saved >= 0
    )
);

-- Unique constraint and indexes
CREATE UNIQUE INDEX idx_daily_aggregates_date_user ON daily_aggregates (analysis_date, user_id_hash);
CREATE INDEX idx_daily_aggregates_date ON daily_aggregates (analysis_date);
```

#### 3. `processing_log` Table
Tracks processing runs and system health.

```sql
CREATE TABLE processing_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Processing run information
    run_date DATE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, completed, failed

    -- Processing statistics
    conversations_processed INTEGER DEFAULT 0,
    conversations_skipped INTEGER DEFAULT 0,
    conversations_failed INTEGER DEFAULT 0,

    -- Performance metrics
    total_llm_requests INTEGER DEFAULT 0,
    total_llm_cost_usd DECIMAL(10,4) DEFAULT 0,
    processing_duration_seconds INTEGER,

    -- Error tracking
    error_message TEXT,
    error_details JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_processing_log_run_date ON processing_log (run_date);
```

---

## Data Models and Entities

### SQLAlchemy Models

```python
# backend/open_webui/cogniforce_models/analytics.py

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, Numeric, Date, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from open_webui.internal.cogniforce_db import CogniforceBase
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime, date
import uuid

class ConversationAnalysis(CogniforceBase):
    __tablename__ = "conversation_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(String(255), nullable=False, unique=True)
    user_id_hash = Column(String(64), nullable=False)

    first_message_at = Column(DateTime(timezone=True), nullable=False)
    last_message_at = Column(DateTime(timezone=True), nullable=False)
    total_duration_minutes = Column(Integer, nullable=False)
    active_duration_minutes = Column(Integer, nullable=False)
    idle_time_minutes = Column(Integer, nullable=False)

    manual_time_low = Column(Integer, nullable=False)
    manual_time_most_likely = Column(Integer, nullable=False)
    manual_time_high = Column(Integer, nullable=False)
    confidence_level = Column(Integer, nullable=False)

    time_saved_minutes = Column(Integer, nullable=False)
    message_count = Column(Integer, nullable=False)

    processed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    processing_version = Column(String(20), default="1.0")

    conversation_summary = Column(Text)
    llm_response = Column(JSON)

    __table_args__ = (
        CheckConstraint('total_duration_minutes >= 0', name='positive_total_duration'),
        CheckConstraint('active_duration_minutes >= 0', name='positive_active_duration'),
        CheckConstraint('time_saved_minutes >= 0', name='positive_time_saved'),
        CheckConstraint('confidence_level BETWEEN 0 AND 100', name='valid_confidence'),
        CheckConstraint('manual_time_low <= manual_time_most_likely', name='valid_estimates_low'),
        CheckConstraint('manual_time_most_likely <= manual_time_high', name='valid_estimates_high'),
    )

class DailyAggregate(CogniforceBase):
    __tablename__ = "daily_aggregates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_date = Column(Date, nullable=False)
    user_id_hash = Column(String(64), nullable=True)  # NULL for global aggregates

    conversation_count = Column(Integer, nullable=False, default=0)
    message_count = Column(Integer, nullable=False, default=0)
    total_active_time = Column(Integer, nullable=False, default=0)
    total_manual_time_estimated = Column(Integer, nullable=False, default=0)
    total_time_saved = Column(Integer, nullable=False, default=0)
    avg_time_saved_per_conversation = Column(Numeric(10, 2))
    avg_confidence_level = Column(Numeric(5, 2))

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('analysis_date', 'user_id_hash', name='unique_daily_aggregate'),
        CheckConstraint('conversation_count >= 0', name='positive_conversation_count'),
        CheckConstraint('total_time_saved >= 0', name='positive_total_time_saved'),
    )

class ProcessingLog(CogniforceBase):
    __tablename__ = "processing_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_date = Column(Date, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(20), nullable=False, default='running')

    conversations_processed = Column(Integer, default=0)
    conversations_skipped = Column(Integer, default=0)
    conversations_failed = Column(Integer, default=0)

    total_llm_requests = Column(Integer, default=0)
    total_llm_cost_usd = Column(Numeric(10, 4), default=0)
    processing_duration_seconds = Column(Integer)

    error_message = Column(Text)
    error_details = Column(JSON)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
```

### Pydantic Models

```python
class ConversationAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: str
    user_id_hash: str
    first_message_at: datetime
    last_message_at: datetime
    total_duration_minutes: int
    active_duration_minutes: int
    time_saved_minutes: int
    confidence_level: int

class DailyAggregateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_date: date
    conversation_count: int
    total_time_saved: int
    avg_time_saved_per_conversation: Optional[float]
    avg_confidence_level: Optional[float]

class AnalyticsSummary(BaseModel):
    total_conversations: int
    total_time_saved: int
    avg_time_saved_per_conversation: float
    confidence_level: float
    daily_trend: List[DailyAggregateResponse]
    user_breakdown: List[Dict[str, Any]]
```

---

## API Endpoints Specification

### Authentication Middleware

```python
# backend/open_webui/routers/analytics.py

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

security = HTTPBearer()

def verify_admin_access(user = Depends(get_admin_user)):
    """Verify user has admin access for analytics"""
    # Uses existing OpenWebUI authentication system
    # get_admin_user dependency ensures only admin users can access
    return user
```

### Core API Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import date, datetime, timedelta

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    days: int = Query(30, ge=1, le=365),
    user_id_hash: Optional[str] = None,
    user = Depends(verify_admin_access)
):
    """Get aggregated analytics summary for the dashboard"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Implementation details...
    return AnalyticsSummary(...)

@router.get("/daily-trend", response_model=List[DailyAggregateResponse])
async def get_daily_trend(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user_id_hash: Optional[str] = None,
    user = Depends(verify_admin_access)
):
    """Get daily time savings trend data"""
    # Implementation details...
    return daily_aggregates

@router.get("/user-breakdown", response_model=List[Dict[str, Any]])
async def get_user_breakdown(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=100),
    user = Depends(verify_admin_access)
):
    """Get top users by time saved"""
    # Implementation details...
    return user_stats

@router.get("/export/csv")
async def export_analytics_csv(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user = Depends(verify_admin_access)
):
    """Export analytics data as CSV"""
    # Generate CSV response
    return StreamingResponse(
        csv_generator(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics-export.csv"}
    )

@router.get("/health")
async def get_analytics_health(
    user = Depends(verify_admin_access)
):
    """Get analytics system health status"""
    latest_run = get_latest_processing_log()
    return {
        "status": "healthy" if latest_run and latest_run.status == "completed" else "unhealthy",
        "last_run": latest_run.completed_at if latest_run else None,
        "next_run": get_next_scheduled_run(),
        "system_info": {
            "timezone": "Europe/Budapest",
            "idle_threshold_minutes": 10,
            "processing_version": "1.0"
        }
    }

@router.post("/trigger-processing")
async def trigger_manual_processing(
    force: bool = Query(False),
    user = Depends(verify_admin_access)
):
    """Manually trigger analytics processing (for testing/backfill)"""
    # Implementation details...
    return {"status": "processing_started", "job_id": job_id}
```

---

## Processing Pipeline Implementation

### Core Processing Logic

```python
# backend/open_webui/services/analytics_processor.py

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
import pytz
from openai import AsyncOpenAI
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

class AnalyticsProcessor:
    def __init__(self, openai_client: AsyncOpenAI, db_session: AsyncSession):
        self.openai_client = openai_client
        self.db_session = db_session
        self.budapest_tz = pytz.timezone('Europe/Budapest')
        self.idle_threshold_minutes = 10

    async def process_daily_analytics(self, target_date: date = None) -> ProcessingLog:
        """Main processing function called by scheduler"""
        if target_date is None:
            target_date = datetime.now(self.budapest_tz).date() - timedelta(days=1)

        log_entry = ProcessingLog(
            run_date=target_date,
            started_at=datetime.now(timezone.utc),
            status='running'
        )

        try:
            # Get new/changed conversations for the target date
            conversations = await self.get_conversations_for_processing(target_date)

            for conversation in conversations:
                try:
                    await self.process_conversation(conversation)
                    log_entry.conversations_processed += 1
                except Exception as e:
                    logger.error(f"Failed to process conversation {conversation.id}: {e}")
                    log_entry.conversations_failed += 1

            # Generate daily aggregates
            await self.generate_daily_aggregates(target_date)

            log_entry.completed_at = datetime.now(timezone.utc)
            log_entry.status = 'completed'
            log_entry.processing_duration_seconds = int(
                (log_entry.completed_at - log_entry.started_at).total_seconds()
            )

        except Exception as e:
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.error_details = {"exception_type": type(e).__name__}
            logger.exception(f"Analytics processing failed for {target_date}")

        finally:
            self.db_session.add(log_entry)
            await self.db_session.commit()

        return log_entry

    async def get_conversations_for_processing(self, target_date: date) -> List[Any]:
        """Get conversations that need processing for the target date"""
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        # Query conversations updated on target date that aren't already processed
        query = select(Chat).where(
            and_(
                Chat.updated_at >= start_of_day.timestamp() * 1000,
                Chat.updated_at <= end_of_day.timestamp() * 1000,
                ~exists().where(ConversationAnalysis.conversation_id == Chat.id)
            )
        )

        result = await self.db_session.execute(query)
        return result.scalars().all()

    async def process_conversation(self, conversation: Chat) -> ConversationAnalysis:
        """Process a single conversation to extract time savings metrics"""

        # Calculate timing metrics
        timing_data = self.calculate_timing_metrics(conversation)

        # Create redacted summary for LLM
        summary = self.create_conversation_summary(conversation)

        # Get LLM time estimates
        llm_estimates = await self.get_llm_time_estimates(summary)

        # Calculate time saved
        time_saved = max(0, llm_estimates['most_likely'] - timing_data['active_minutes'])

        # Create analysis record
        analysis = ConversationAnalysis(
            conversation_id=conversation.id,
            user_id_hash=self.hash_user_id(conversation.user_id),

            first_message_at=timing_data['first_message_at'],
            last_message_at=timing_data['last_message_at'],
            total_duration_minutes=timing_data['total_minutes'],
            active_duration_minutes=timing_data['active_minutes'],
            idle_time_minutes=timing_data['idle_minutes'],

            manual_time_low=llm_estimates['low'],
            manual_time_most_likely=llm_estimates['most_likely'],
            manual_time_high=llm_estimates['high'],
            confidence_level=llm_estimates['confidence'],

            time_saved_minutes=time_saved,
            message_count=len(conversation.chat.get('messages', [])),

            conversation_summary=summary,
            llm_response=llm_estimates['raw_response']
        )

        self.db_session.add(analysis)
        await self.db_session.commit()

        return analysis

    def calculate_timing_metrics(self, conversation: Chat) -> Dict[str, Any]:
        """Calculate active time, idle time, and duration metrics"""
        messages = conversation.chat.get('messages', [])
        if not messages:
            return self.empty_timing_metrics()

        # Sort messages by timestamp
        timestamps = []
        for msg in messages:
            if 'timestamp' in msg:
                timestamps.append(datetime.fromtimestamp(msg['timestamp'], tz=timezone.utc))

        if len(timestamps) < 2:
            return self.empty_timing_metrics()

        timestamps.sort()
        first_message = timestamps[0]
        last_message = timestamps[-1]

        # Calculate active time (excluding idle gaps > threshold)
        active_minutes = 0
        for i in range(1, len(timestamps)):
            gap_minutes = (timestamps[i] - timestamps[i-1]).total_seconds() / 60
            if gap_minutes <= self.idle_threshold_minutes:
                active_minutes += gap_minutes

        total_minutes = (last_message - first_message).total_seconds() / 60
        idle_minutes = total_minutes - active_minutes

        return {
            'first_message_at': first_message,
            'last_message_at': last_message,
            'total_minutes': int(total_minutes),
            'active_minutes': int(active_minutes),
            'idle_minutes': int(idle_minutes)
        }

    def create_conversation_summary(self, conversation: Chat) -> str:
        """Create a redacted, compact summary of the conversation for LLM analysis"""
        messages = conversation.chat.get('messages', [])

        # Extract key information while removing PII
        summary_parts = []
        summary_parts.append(f"Task type: {self.infer_task_type(messages)}")
        summary_parts.append(f"Message count: {len(messages)}")
        summary_parts.append(f"User queries: {self.count_user_queries(messages)}")
        summary_parts.append(f"AI responses: {self.count_ai_responses(messages)}")

        # Add redacted content samples
        user_messages = [msg.get('content', '') for msg in messages if msg.get('role') == 'user']
        if user_messages:
            # Redact PII and get representative samples
            sample_content = self.redact_and_sample_content(user_messages[:3])
            summary_parts.append(f"Sample queries: {sample_content}")

        return " | ".join(summary_parts)

    async def get_llm_time_estimates(self, conversation_summary: str) -> Dict[str, Any]:
        """Get time estimates from OpenAI for manual task completion"""

        prompt = f"""
        Analyze this AI-assisted conversation and estimate how long it would take a human to complete the same task manually (without AI assistance).

        Conversation summary: {conversation_summary}

        Please provide:
        1. Low estimate (optimistic scenario) in minutes
        2. Most likely estimate (realistic scenario) in minutes
        3. High estimate (pessimistic scenario) in minutes
        4. Confidence level (0-100) in your estimates

        Consider factors like:
        - Research time
        - Writing/composition time
        - Problem-solving complexity
        - Required expertise level
        - Task verification time

        Respond in this exact JSON format:
        {{
            "low": <number>,
            "most_likely": <number>,
            "high": <number>,
            "confidence": <number>,
            "reasoning": "<brief explanation>"
        }}
        """

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective model for estimates
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1  # Low temperature for consistent estimates
            )

            content = response.choices[0].message.content
            estimates = json.loads(content)
            estimates['raw_response'] = content

            # Validate estimates
            if not all(key in estimates for key in ['low', 'most_likely', 'high', 'confidence']):
                raise ValueError("Missing required estimate fields")

            if not (estimates['low'] <= estimates['most_likely'] <= estimates['high']):
                raise ValueError("Invalid estimate ordering")

            return estimates

        except Exception as e:
            logger.error(f"LLM estimation failed: {e}")
            # Return conservative fallback estimates
            return {
                'low': 30,
                'most_likely': 60,
                'high': 120,
                'confidence': 50,
                'reasoning': f"Fallback due to error: {str(e)}",
                'raw_response': None
            }

    async def generate_daily_aggregates(self, target_date: date):
        """Generate and store daily aggregate statistics"""

        # Global aggregates
        global_stats = await self.calculate_daily_stats(target_date, user_id_hash=None)
        await self.store_daily_aggregate(target_date, None, global_stats)

        # Per-user aggregates for top users
        user_stats = await self.calculate_user_daily_stats(target_date)
        for user_id_hash, stats in user_stats.items():
            await self.store_daily_aggregate(target_date, user_id_hash, stats)

    def hash_user_id(self, user_id: str) -> str:
        """Create a privacy-preserving hash of user ID"""
        return hashlib.sha256(f"{user_id}:{ANALYTICS_SALT}".encode()).hexdigest()

    # Additional utility methods...
```

---

## Scheduling and Configuration

### APScheduler Setup

```python
# backend/open_webui/services/analytics_scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging

logger = logging.getLogger(__name__)

class AnalyticsScheduler:
    def __init__(self, processor: AnalyticsProcessor):
        self.processor = processor
        self.scheduler = AsyncIOScheduler()
        self.budapest_tz = pytz.timezone('Europe/Budapest')

    def start(self):
        """Start the analytics scheduler"""

        # Daily processing at 00:00 Budapest time
        self.scheduler.add_job(
            func=self.processor.process_daily_analytics,
            trigger=CronTrigger(
                hour=0,
                minute=0,
                timezone=self.budapest_tz
            ),
            id='daily_analytics_processing',
            name='Daily Analytics Processing',
            max_instances=1,  # Prevent overlapping runs
            misfire_grace_time=3600  # 1 hour grace period
        )

        # Health check job (every 6 hours)
        self.scheduler.add_job(
            func=self.run_health_check,
            trigger=CronTrigger(
                hour='*/6',
                timezone=self.budapest_tz
            ),
            id='analytics_health_check',
            name='Analytics Health Check'
        )

        self.scheduler.start()
        logger.info("Analytics scheduler started")

    def stop(self):
        """Stop the scheduler gracefully"""
        self.scheduler.shutdown(wait=True)
        logger.info("Analytics scheduler stopped")

    async def run_health_check(self):
        """Check system health and log warnings"""
        try:
            latest_log = await self.get_latest_processing_log()
            if not latest_log or latest_log.status != 'completed':
                logger.warning("Analytics processing appears to be failing")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
```

### Environment Configuration

```python
# backend/open_webui/config/analytics.py

import os
from typing import Optional

class AnalyticsConfig:
    # Database Configuration
    COGNIFORCE_DATABASE_URL: str = os.environ.get(
        "COGNIFORCE_DATABASE_URL",
        "postgresql://username:password@localhost/cogniforce"
    )

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.environ.get("ANALYTICS_OPENAI_MODEL", "gpt-4o-mini")

    # Security Configuration
    ANALYTICS_SALT: str = os.environ.get("ANALYTICS_SALT", "analytics_hash_salt")

    # Processing Configuration
    TIMEZONE: str = os.environ.get("TZ", "Europe/Budapest")
    IDLE_THRESHOLD_MINUTES: int = int(os.environ.get("ANALYTICS_IDLE_THRESHOLD", "10"))
    MAX_CONVERSATIONS_PER_RUN: int = int(os.environ.get("ANALYTICS_MAX_CONVERSATIONS", "1000"))

    # Rate Limiting
    LLM_REQUESTS_PER_MINUTE: int = int(os.environ.get("ANALYTICS_LLM_RPM", "50"))

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        required_vars = ["COGNIFORCE_DATABASE_URL", "OPENAI_API_KEY"]
        missing_vars = [var for var in required_vars if not getattr(cls, var)]

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")

        return True

# Environment Variables Documentation
"""
Required Environment Variables:
- COGNIFORCE_DATABASE_URL: PostgreSQL connection string for cogniforce database
- OPENAI_API_KEY: OpenAI API key for time estimates

Optional Environment Variables:
- ANALYTICS_SALT: Salt for user ID hashing (default: analytics_hash_salt)
- TZ: Timezone for scheduling (default: Europe/Budapest)
- ANALYTICS_IDLE_THRESHOLD: Minutes before considering time as idle (default: 10)
- ANALYTICS_MAX_CONVERSATIONS: Max conversations per processing run (default: 1000)
- ANALYTICS_LLM_RPM: LLM requests per minute limit (default: 50)
- ANALYTICS_OPENAI_MODEL: OpenAI model for estimates (default: gpt-4o-mini)
"""
```

---

## Integration with Open WebUI

### Main Application Integration

```python
# backend/open_webui/main.py (additions)

from open_webui.routers.analytics import router as analytics_router
from open_webui.services.analytics_scheduler import AnalyticsScheduler
from open_webui.services.analytics_processor import AnalyticsProcessor
from open_webui.config.analytics import AnalyticsConfig
from open_webui.internal.cogniforce_db import get_cogniforce_session

# Add analytics router
app.include_router(analytics_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Existing startup code...

    # Initialize analytics if configured
    if AnalyticsConfig.validate():
        try:
            analytics_processor = AnalyticsProcessor(
                openai_client=AsyncOpenAI(api_key=AnalyticsConfig.OPENAI_API_KEY),
                db_session=get_cogniforce_session()
            )

            analytics_scheduler = AnalyticsScheduler(analytics_processor)
            analytics_scheduler.start()

            app.state.analytics_scheduler = analytics_scheduler
            logger.info("Analytics system initialized")

        except Exception as e:
            logger.error(f"Failed to initialize analytics: {e}")

    yield

    # Cleanup analytics scheduler
    if hasattr(app.state, 'analytics_scheduler'):
        app.state.analytics_scheduler.stop()
```

### Database Connection Management

```python
# This functionality is now integrated into the existing cogniforce_db.py module
# backend/open_webui/internal/cogniforce_db.py provides:
# - get_cogniforce_session(): Database session for cogniforce database
# - CogniforceBase: SQLAlchemy declarative base for cogniforce models
# - Automatic database creation and migration execution
# - Connection management for the cogniforce database

# The cogniforce database contains all analytics tables alongside
# the existing conversation_insights and user_engagement tables
# from the dual-database setup.

# Usage example:
# from open_webui.internal.cogniforce_db import get_cogniforce_session
#
# async def get_analytics_data():
#     with get_cogniforce_session() as session:
#         # Query analytics tables
#         pass
```

---

## CLI Tools and Utilities

### Management CLI

```python
# backend/open_webui/cli/analytics.py

import click
import asyncio
from datetime import date, datetime, timedelta
from open_webui.services.analytics_processor import AnalyticsProcessor
from open_webui.internal.cogniforce_db import get_cogniforce_session

@click.group()
def analytics():
    """Analytics management commands"""
    pass

@analytics.command()
@click.option('--start-date', type=click.DateTime(['%Y-%m-%d']), required=True)
@click.option('--end-date', type=click.DateTime(['%Y-%m-%d']), required=True)
@click.option('--force', is_flag=True, help='Reprocess existing data')
def backfill(start_date: datetime, end_date: datetime, force: bool):
    """Backfill analytics data for a date range"""

    async def run_backfill():
        async with get_cogniforce_session() as session:
            processor = AnalyticsProcessor(openai_client, session)

            current_date = start_date.date()
            while current_date <= end_date.date():
                click.echo(f"Processing {current_date}")

                if force:
                    # Delete existing data for reprocessing
                    await processor.delete_analysis_for_date(current_date)

                await processor.process_daily_analytics(current_date)
                current_date += timedelta(days=1)

    asyncio.run(run_backfill())
    click.echo("Backfill completed")

@analytics.command()
def health():
    """Check analytics system health"""

    async def check_health():
        # Implementation...
        pass

    asyncio.run(check_health())

@analytics.command()
@click.option('--days', default=7, help='Number of days to show')
def stats(days: int):
    """Show analytics statistics"""

    async def show_stats():
        # Implementation...
        pass

    asyncio.run(show_stats())

if __name__ == '__main__':
    analytics()
```

---

## Security Considerations

### Data Privacy
- **User ID Hashing**: All user identifiers are SHA-256 hashed with salt before storage
- **Content Redaction**: Conversation summaries remove PII before LLM analysis
- **Access Control**: Analytics endpoints protected by environment-configurable password
- **Separate Database**: Analytics data isolated from main application database

### API Security
- **Bearer Token Authentication**: Password-based access control for all endpoints
- **Rate Limiting**: Configurable limits on LLM API requests
- **Input Validation**: Strict validation of all query parameters and date ranges
- **Error Handling**: Sanitized error messages to prevent information disclosure

### Configuration Security
```bash
# Production environment variables
ANALYTICS_SALT="unique_salt_for_user_hashing"
COGNIFORCE_DATABASE_URL="postgresql://cogniforce_user:secure_password@cogniforce_db:5432/cogniforce"
OPENAI_API_KEY="sk-your_openai_api_key_here"
```

---

## Testing Strategy

### Unit Tests
```python
# tests/test_analytics_processor.py

import pytest
from unittest.mock import AsyncMock, Mock
from open_webui.services.analytics_processor import AnalyticsProcessor
from datetime import datetime, date

class TestAnalyticsProcessor:

    @pytest.fixture
    def processor(self):
        openai_client = AsyncMock()
        db_session = AsyncMock()
        return AnalyticsProcessor(openai_client, db_session)

    def test_calculate_timing_metrics(self, processor):
        """Test timing calculation logic"""
        conversation = Mock()
        conversation.chat = {
            'messages': [
                {'timestamp': 1640995200, 'role': 'user'},  # 2022-01-01 00:00:00
                {'timestamp': 1640995800, 'role': 'assistant'},  # +10 minutes
                {'timestamp': 1640999400, 'role': 'user'},  # +60 minutes (idle gap)
            ]
        }

        result = processor.calculate_timing_metrics(conversation)

        assert result['total_minutes'] == 70  # Total duration
        assert result['active_minutes'] == 10  # Only first 10 minutes (gap > threshold)
        assert result['idle_minutes'] == 60

    @pytest.mark.asyncio
    async def test_llm_time_estimates(self, processor):
        """Test LLM estimation with mock response"""
        processor.openai_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content='{"low": 30, "most_likely": 60, "high": 120, "confidence": 85, "reasoning": "test"}'))]
        )

        result = await processor.get_llm_time_estimates("Test conversation summary")

        assert result['low'] == 30
        assert result['most_likely'] == 60
        assert result['high'] == 120
        assert result['confidence'] == 85
```

### Integration Tests
```python
# tests/test_analytics_api.py

import pytest
from fastapi.testclient import TestClient
from open_webui.main import app

class TestAnalyticsAPI:

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_analytics_summary_auth_required(self, client):
        """Test that analytics endpoints require authentication"""
        response = client.get("/api/v1/analytics/summary")
        assert response.status_code == 401

    def test_analytics_summary_with_auth(self, client):
        """Test analytics summary with valid auth"""
        headers = {"Authorization": "Bearer test_password"}
        response = client.get("/api/v1/analytics/summary", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "total_conversations" in data
        assert "total_time_saved" in data
```

---

## Deployment and Migration

### Database Migration Script
```sql
-- migrations/001_create_analytics_tables.sql

-- Create analytics database if it doesn't exist
-- CREATE DATABASE analytics_db;

-- Create UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create conversation_analysis table
CREATE TABLE IF NOT EXISTS conversation_analysis (
    -- Schema definition from above
);

-- Create daily_aggregates table
CREATE TABLE IF NOT EXISTS daily_aggregates (
    -- Schema definition from above
);

-- Create processing_log table
CREATE TABLE IF NOT EXISTS processing_log (
    -- Schema definition from above
);

-- Create all indexes
CREATE INDEX IF NOT EXISTS idx_conversation_analysis_user_date ON conversation_analysis (user_id_hash, DATE(processed_at));
-- Additional indexes...
```

### Docker Configuration
```yaml
# docker-compose.cogniforce.yml

version: '3.8'

services:
  cogniforce-db:
    image: postgres:15
    environment:
      POSTGRES_DB: cogniforce
      POSTGRES_USER: cogniforce_user
      POSTGRES_PASSWORD: ${COGNIFORCE_DB_PASSWORD}
    volumes:
      - cogniforce_data:/var/lib/postgresql/data
      - ./cogniforce_migrations:/docker-entrypoint-initdb.d
    ports:
      - "5433:5432"
    networks:
      - cogniforce_network

  open-webui:
    # Existing service configuration
    environment:
      - COGNIFORCE_DATABASE_URL=postgresql://cogniforce_user:${COGNIFORCE_DB_PASSWORD}@cogniforce-db:5432/cogniforce
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANALYTICS_SALT=${ANALYTICS_SALT}
    depends_on:
      - cogniforce-db
    networks:
      - cogniforce_network
      - default

volumes:
  cogniforce_data:

networks:
  cogniforce_network:
```

---

## Cost and Performance Considerations

### OpenAI API Costs
- **Model**: GPT-4o-mini (~$0.00015/1K tokens)
- **Estimated usage**: ~200 tokens per conversation analysis
- **Daily cost estimate**: For 1000 conversations/day ≈ $0.03/day
- **Monthly cost**: ~$1/month for moderate usage

### Performance Optimization
- **Batch Processing**: Process conversations in configurable batches
- **Database Indexing**: Optimized indexes for common query patterns
- **Connection Pooling**: Efficient database connection management
- **Async Processing**: Non-blocking I/O for better throughput

### Scaling Considerations
- **Horizontal Scaling**: Processing can be distributed across multiple workers
- **Database Partitioning**: Partition large tables by date for better performance
- **Caching**: Cache frequently accessed aggregates
- **Archive Strategy**: Archive old detailed data, keep aggregates

---

## Future Enhancements

### Advanced Features
1. **Advanced Analytics**
   - Task category classification
   - Productivity trend analysis
   - Team/department-level analytics
   - Custom time period analysis

2. **Enhanced Dashboard**
   - Interactive charts with drill-down
   - Real-time processing status
   - Custom report generation
   - Email/Slack notifications

3. **Integration Improvements**
   - Webhook support for real-time processing
   - Integration with external analytics tools
   - Advanced export formats (Excel, PDF)
   - API rate limiting and quotas

### Technical Improvements
- **Machine Learning**: Train custom models for better time estimates
- **Performance**: Implement caching layers and optimize queries
- **Monitoring**: Advanced metrics and alerting
- **Security**: Enhanced authentication options (OAuth, SAML)

---

## Conclusion

This specification provides a comprehensive foundation for implementing the AI Time Savings Analytics backend system. The modular design allows for incremental implementation and future enhancements while maintaining security, performance, and scalability requirements.

Key system components:
1. **Core Infrastructure**: Database models, API endpoints, basic processing
2. **Scheduling System**: APScheduler integration and daily processing
3. **Dashboard Integration**: Backend APIs serving frontend requirements
4. **Testing & Deployment**: Comprehensive testing and production deployment
5. **Monitoring & Optimization**: Performance monitoring and cost optimization

The system is designed to provide valuable insights into AI-assisted productivity while maintaining user privacy and system security.