"""Initial Cogniforce analytics schema with proper date attribution

This migration creates the complete analytics schema including the critical fix
for date attribution where time savings are attributed to when chats occurred,
not when they were processed.

Revision ID: cf001_complete
Revises:
Create Date: 2025-09-29

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from open_webui.internal.db import JSONField
import uuid

# revision identifiers, used by Alembic.
revision: str = 'cf001_complete'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    """Create complete analytics schema with proper date attribution."""

    # ChatAnalysis table - stores per-chat analysis results
    op.create_table('chat_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),

        # Source chat identification
        sa.Column('chat_id', sa.String(255), nullable=False, unique=True),
        sa.Column('user_id', sa.String(255), nullable=False),  # OpenWebUI user ID

        # CRITICAL FIX: Date when chat actually occurred (not when processed)
        sa.Column('chat_date', sa.Date(), nullable=False),

        # Timing analysis
        sa.Column('first_message_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('active_duration_minutes', sa.Integer(), nullable=False),  # Excluding idle gaps >10min
        sa.Column('idle_time_minutes', sa.Integer(), nullable=False),

        # LLM time estimates (in minutes)
        sa.Column('manual_time_low', sa.Integer(), nullable=False),
        sa.Column('manual_time_most_likely', sa.Integer(), nullable=False),
        sa.Column('manual_time_high', sa.Integer(), nullable=False),
        sa.Column('confidence_level', sa.Integer(), nullable=False),  # 0-100

        # Calculated savings
        sa.Column('time_saved_minutes', sa.Integer(), nullable=False),  # max(0, manual_most_likely - active_minutes)

        # Metadata
        sa.Column('message_count', sa.Integer(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('processing_version', sa.String(20), default="1.0"),

        # Analysis data
        sa.Column('chat_summary', sa.Text(), nullable=True),  # Redacted summary sent to LLM
        sa.Column('llm_response', JSONField(), nullable=True),  # Full LLM response for debugging

        # Constraints
        sa.CheckConstraint(
            'total_duration_minutes >= 0 AND '
            'active_duration_minutes >= 0 AND '
            'idle_time_minutes >= 0 AND '
            'time_saved_minutes >= 0',
            name='positive_durations'
        ),
        sa.CheckConstraint(
            'confidence_level BETWEEN 0 AND 100',
            name='valid_confidence'
        ),
        sa.CheckConstraint(
            'manual_time_low <= manual_time_most_likely AND '
            'manual_time_most_likely <= manual_time_high',
            name='valid_estimates'
        ),
    )

    # DailyAggregate table - pre-computed daily statistics for dashboard performance
    op.create_table('daily_aggregates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),

        # Aggregation period - CRITICAL: Uses chat occurrence date, not processing date
        sa.Column('analysis_date', sa.Date(), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=True),  # NULL for global aggregates

        # Counts
        sa.Column('chat_count', sa.Integer(), nullable=False, default=0),
        sa.Column('message_count', sa.Integer(), nullable=False, default=0),

        # Time metrics (in minutes)
        sa.Column('total_active_time', sa.Integer(), nullable=False, default=0),
        sa.Column('total_manual_time_estimated', sa.Integer(), nullable=False, default=0),
        sa.Column('total_time_saved', sa.Integer(), nullable=False, default=0),
        sa.Column('avg_time_saved_per_chat', sa.Float(), nullable=True),

        # Confidence metrics
        sa.Column('avg_confidence_level', sa.Float(), nullable=True),

        # Processing metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),

        # Constraints
        sa.UniqueConstraint('analysis_date', 'user_id', name='unique_daily_aggregate'),
        sa.CheckConstraint(
            'chat_count >= 0 AND '
            'message_count >= 0 AND '
            'total_active_time >= 0 AND '
            'total_time_saved >= 0',
            name='positive_aggregates'
        ),
    )

    # ProcessingLog table - audit trail for processing runs
    op.create_table('processing_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),

        # Processing run identification
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),  # 'running', 'completed', 'failed'
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

        # Processing results
        sa.Column('chats_processed', sa.Integer(), nullable=True, default=0),
        sa.Column('chats_skipped', sa.Integer(), nullable=True, default=0),
        sa.Column('chats_failed', sa.Integer(), nullable=True, default=0),

        # Performance metrics
        sa.Column('total_llm_requests', sa.Integer(), nullable=True, default=0),
        sa.Column('total_llm_cost_usd', sa.Float(), nullable=True, default=0.0),
        sa.Column('processing_duration_seconds', sa.Integer(), nullable=True),

        # Legacy fields for compatibility
        sa.Column('total_cost_usd', sa.Float(), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),

        # Error details
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', JSONField(), nullable=True),

        # Processing metadata
        sa.Column('processing_version', sa.String(20), default="1.0"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for performance
    op.create_index('idx_chat_analysis_chat_date', 'chat_analysis', ['chat_date'])
    op.create_index('idx_chat_analysis_user_id', 'chat_analysis', ['user_id'])
    op.create_index('idx_chat_analysis_processed_at', 'chat_analysis', ['processed_at'])

    op.create_index('idx_daily_aggregates_date', 'daily_aggregates', ['analysis_date'])
    op.create_index('idx_daily_aggregates_user_date', 'daily_aggregates', ['user_id', 'analysis_date'])

    op.create_index('idx_processing_log_target_date', 'processing_log', ['target_date'])
    op.create_index('idx_processing_log_status', 'processing_log', ['status'])


def downgrade():
    """Drop all analytics tables."""

    # Drop indexes first
    op.drop_index('idx_processing_log_status', table_name='processing_log')
    op.drop_index('idx_processing_log_target_date', table_name='processing_log')

    op.drop_index('idx_daily_aggregates_user_date', table_name='daily_aggregates')
    op.drop_index('idx_daily_aggregates_date', table_name='daily_aggregates')

    op.drop_index('idx_chat_analysis_processed_at', table_name='chat_analysis')
    op.drop_index('idx_chat_analysis_user_id', table_name='chat_analysis')
    op.drop_index('idx_chat_analysis_chat_date', table_name='chat_analysis')

    # Drop tables
    op.drop_table('processing_log')
    op.drop_table('daily_aggregates')
    op.drop_table('chat_analysis')