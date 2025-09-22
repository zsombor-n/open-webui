import time
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import BigInteger, Column, String, Text, Integer, Float
from open_webui.internal.cogniforce_db import CogniforceBase
from open_webui.internal.db import JSONField

####################
# Analytics Models
####################

class ConversationInsights(CogniforceBase):
    """Analytics for conversation patterns and insights."""
    __tablename__ = "conversation_insights"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)

    # Analytics metrics
    message_count = Column(Integer, default=0)
    avg_response_time = Column(Float, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    topics = Column(JSONField, nullable=True)  # Array of identified topics

    # Metadata
    insights_metadata = Column(JSONField, nullable=True)
    created_at = Column(BigInteger, default=lambda: int(time.time()))
    updated_at = Column(BigInteger, default=lambda: int(time.time()))

class UserEngagement(CogniforceBase):
    """User engagement metrics and patterns."""
    __tablename__ = "user_engagement"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)

    # Engagement metrics
    daily_active_days = Column(Integer, default=0)
    total_conversations = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    avg_session_duration = Column(Float, nullable=True)

    # Time-based analytics
    last_activity_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, default=lambda: int(time.time()))
    updated_at = Column(BigInteger, default=lambda: int(time.time()))

####################
# Pydantic Models
####################

class ConversationInsightsModel(BaseModel):
    id: str
    user_id: str
    conversation_id: str
    message_count: int = 0
    avg_response_time: Optional[float] = None
    sentiment_score: Optional[float] = None
    topics: Optional[list] = None
    insights_metadata: Optional[dict] = None
    created_at: int
    updated_at: int

class UserEngagementModel(BaseModel):
    id: str
    user_id: str
    daily_active_days: int = 0
    total_conversations: int = 0
    total_messages: int = 0
    avg_session_duration: Optional[float] = None
    last_activity_at: Optional[int] = None
    created_at: int
    updated_at: int