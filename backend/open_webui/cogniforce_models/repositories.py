"""
Cogniforce Database Repositories
Example usage of the dual database setup
"""
import time
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from open_webui.internal.cogniforce_db import get_cogniforce_session
from open_webui.cogniforce_models.analytics import (
    ConversationInsights,
    UserEngagement,
    ConversationInsightsModel,
    UserEngagementModel,
)


class ConversationInsightsRepository:
    """Repository for conversation insights operations."""

    @staticmethod
    def create_insights(
        user_id: str,
        conversation_id: str,
        message_count: int = 0,
        avg_response_time: Optional[float] = None,
        sentiment_score: Optional[float] = None,
        topics: Optional[list] = None,
        metadata: Optional[dict] = None,
    ) -> ConversationInsightsModel:
        """Create a new conversation insights record."""
        with get_cogniforce_session() as session:
            insights = ConversationInsights(
                id=str(uuid.uuid4()),
                user_id=user_id,
                conversation_id=conversation_id,
                message_count=message_count,
                avg_response_time=avg_response_time,
                sentiment_score=sentiment_score,
                topics=topics,
                insights_metadata=metadata,
                created_at=int(time.time()),
                updated_at=int(time.time()),
            )
            session.add(insights)
            session.commit()
            session.refresh(insights)

            return ConversationInsightsModel.model_validate(insights.__dict__)

    @staticmethod
    def get_user_conversations(user_id: str) -> List[ConversationInsightsModel]:
        """Get all conversation insights for a user."""
        with get_cogniforce_session() as session:
            insights = (
                session.query(ConversationInsights)
                .filter(ConversationInsights.user_id == user_id)
                .all()
            )
            return [ConversationInsightsModel.model_validate(i.__dict__) for i in insights]

    @staticmethod
    def update_conversation_metrics(
        conversation_id: str,
        message_count: Optional[int] = None,
        avg_response_time: Optional[float] = None,
        sentiment_score: Optional[float] = None,
    ) -> Optional[ConversationInsightsModel]:
        """Update metrics for an existing conversation insights."""
        with get_cogniforce_session() as session:
            insights = (
                session.query(ConversationInsights)
                .filter(ConversationInsights.conversation_id == conversation_id)
                .first()
            )

            if insights:
                if message_count is not None:
                    insights.message_count = message_count
                if avg_response_time is not None:
                    insights.avg_response_time = avg_response_time
                if sentiment_score is not None:
                    insights.sentiment_score = sentiment_score

                insights.updated_at = int(time.time())
                session.commit()
                session.refresh(insights)

                return ConversationInsightsModel.model_validate(insights.__dict__)

            return None


class UserEngagementRepository:
    """Repository for user engagement operations."""

    @staticmethod
    def create_or_update_engagement(
        user_id: str,
        daily_active_days: int = 0,
        total_conversations: int = 0,
        total_messages: int = 0,
        avg_session_duration: Optional[float] = None,
    ) -> UserEngagementModel:
        """Create or update user engagement metrics."""
        with get_cogniforce_session() as session:
            engagement = (
                session.query(UserEngagement)
                .filter(UserEngagement.user_id == user_id)
                .first()
            )

            if engagement:
                # Update existing record
                engagement.daily_active_days = daily_active_days
                engagement.total_conversations = total_conversations
                engagement.total_messages = total_messages
                engagement.avg_session_duration = avg_session_duration
                engagement.last_activity_at = int(time.time())
                engagement.updated_at = int(time.time())
            else:
                # Create new record
                engagement = UserEngagement(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    daily_active_days=daily_active_days,
                    total_conversations=total_conversations,
                    total_messages=total_messages,
                    avg_session_duration=avg_session_duration,
                    last_activity_at=int(time.time()),
                    created_at=int(time.time()),
                    updated_at=int(time.time()),
                )
                session.add(engagement)

            session.commit()
            session.refresh(engagement)

            return UserEngagementModel.model_validate(engagement.__dict__)

    @staticmethod
    def get_user_engagement(user_id: str) -> Optional[UserEngagementModel]:
        """Get engagement metrics for a specific user."""
        with get_cogniforce_session() as session:
            engagement = (
                session.query(UserEngagement)
                .filter(UserEngagement.user_id == user_id)
                .first()
            )

            if engagement:
                return UserEngagementModel.model_validate(engagement.__dict__)

            return None

    @staticmethod
    def get_top_engaged_users(limit: int = 10) -> List[UserEngagementModel]:
        """Get the most engaged users by total conversations."""
        with get_cogniforce_session() as session:
            engagements = (
                session.query(UserEngagement)
                .order_by(UserEngagement.total_conversations.desc())
                .limit(limit)
                .all()
            )

            return [UserEngagementModel.model_validate(e.__dict__) for e in engagements]


# Example usage functions
def example_dual_database_usage():
    """
    Example demonstrating how to use both databases simultaneously.
    This function shows how OpenWebUI data and Cogniforce analytics
    can be used together while maintaining complete separation.
    """

    # Using OpenWebUI database (existing functionality)
    from open_webui.models.users import Users  # OpenWebUI database
    from open_webui.internal.db import get_db    # OpenWebUI database

    # Example: Get user from OpenWebUI database
    with get_db() as openwebui_session:
        # This uses the original OpenWebUI database
        users = openwebui_session.query(Users).limit(5).all()

    # Using Cogniforce database (new analytics)
    # This uses the separate Cogniforce database
    for user in users:
        # Create analytics for this user in Cogniforce database
        engagement = UserEngagementRepository.create_or_update_engagement(
            user_id=user.id,
            daily_active_days=1,
            total_conversations=5,
            total_messages=50,
            avg_session_duration=15.5,
        )

        # Create conversation insights in Cogniforce database
        insights = ConversationInsightsRepository.create_insights(
            user_id=user.id,
            conversation_id=f"conv_{uuid.uuid4()}",
            message_count=10,
            avg_response_time=2.3,
            sentiment_score=0.8,
            topics=["technology", "AI", "programming"],
            metadata={"source": "web_chat", "session_length": 20},
        )

    # Query analytics from Cogniforce database
    top_users = UserEngagementRepository.get_top_engaged_users(limit=5)

    print(f"Created analytics for {len(users)} users")
    print(f"Top {len(top_users)} engaged users by conversations")

    return {"users_processed": len(users), "top_engaged": len(top_users)}