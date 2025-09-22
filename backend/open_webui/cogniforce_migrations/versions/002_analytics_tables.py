"""Analytics tables for time savings analysis

Revision ID: cf002_analytics
Revises: cf001_initial
Create Date: 2025-01-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from open_webui.internal.db import JSONField

# revision identifiers, used by Alembic.
revision: str = 'cf002_analytics'
down_revision: Union[str, None] = 'cf001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create analytics tables for time savings analysis."""

    # Create conversation_analysis table
    op.create_table(
        'conversation_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),

        # Source conversation identification
        sa.Column('conversation_id', sa.String(255), nullable=False),
        sa.Column('user_id_hash', sa.String(64), nullable=False),

        # Timing analysis
        sa.Column('first_message_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('active_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('idle_time_minutes', sa.Integer(), nullable=False),

        # LLM time estimates (in minutes)
        sa.Column('manual_time_low', sa.Integer(), nullable=False),
        sa.Column('manual_time_most_likely', sa.Integer(), nullable=False),
        sa.Column('manual_time_high', sa.Integer(), nullable=False),
        sa.Column('confidence_level', sa.Integer(), nullable=False),

        # Calculated savings
        sa.Column('time_saved_minutes', sa.Integer(), nullable=False),

        # Metadata
        sa.Column('message_count', sa.Integer(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_version', sa.String(20), nullable=True),

        # Analysis data
        sa.Column('conversation_summary', sa.Text(), nullable=True),
        sa.Column('llm_response', JSONField(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id'),

        # Check constraints
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
        )
    )

    # Create daily_aggregates table
    op.create_table(
        'daily_aggregates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),

        # Aggregation period
        sa.Column('analysis_date', sa.Date(), nullable=False),
        sa.Column('user_id_hash', sa.String(64), nullable=True),  # NULL for global aggregates

        # Counts
        sa.Column('conversation_count', sa.Integer(), nullable=False, default=0),
        sa.Column('message_count', sa.Integer(), nullable=False, default=0),

        # Time metrics (in minutes)
        sa.Column('total_active_time', sa.Integer(), nullable=False, default=0),
        sa.Column('total_manual_time_estimated', sa.Integer(), nullable=False, default=0),
        sa.Column('total_time_saved', sa.Integer(), nullable=False, default=0),
        sa.Column('avg_time_saved_per_conversation', sa.Float(), nullable=True),

        # Confidence metrics
        sa.Column('avg_confidence_level', sa.Float(), nullable=True),

        # Processing metadata
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_date', 'user_id_hash', name='unique_daily_aggregate'),

        # Check constraints
        sa.CheckConstraint(
            'conversation_count >= 0 AND '
            'message_count >= 0 AND '
            'total_active_time >= 0 AND '
            'total_time_saved >= 0',
            name='positive_aggregates'
        )
    )

    # Create processing_log table
    op.create_table(
        'processing_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),

        # Processing run information
        sa.Column('run_date', sa.Date(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='running'),

        # Processing statistics
        sa.Column('conversations_processed', sa.Integer(), nullable=True, default=0),
        sa.Column('conversations_skipped', sa.Integer(), nullable=True, default=0),
        sa.Column('conversations_failed', sa.Integer(), nullable=True, default=0),

        # Performance metrics
        sa.Column('total_llm_requests', sa.Integer(), nullable=True, default=0),
        sa.Column('total_llm_cost_usd', sa.Float(), nullable=True, default=0.0),
        sa.Column('processing_duration_seconds', sa.Integer(), nullable=True),

        # Error tracking
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', JSONField(), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),

        # Check constraints
        sa.CheckConstraint(
            'conversations_processed >= 0 AND '
            'conversations_skipped >= 0 AND '
            'conversations_failed >= 0',
            name='positive_processing_counts'
        )
    )

    # Create indexes for performance

    # Conversation analysis indexes
    op.create_index(
        'idx_conversation_analysis_user_date',
        'conversation_analysis',
        ['user_id_hash', 'processed_at']
    )
    op.create_index(
        'idx_conversation_analysis_processed_at',
        'conversation_analysis',
        ['processed_at']
    )

    # Daily aggregates indexes
    op.create_index(
        'idx_daily_aggregates_date',
        'daily_aggregates',
        ['analysis_date']
    )

    # Processing log indexes
    op.create_index(
        'idx_processing_log_run_date',
        'processing_log',
        ['run_date']
    )


def downgrade() -> None:
    """Drop analytics tables."""

    # Drop indexes first
    op.drop_index('idx_processing_log_run_date', table_name='processing_log')
    op.drop_index('idx_daily_aggregates_date', table_name='daily_aggregates')
    op.drop_index('idx_conversation_analysis_processed_at', table_name='conversation_analysis')
    op.drop_index('idx_conversation_analysis_user_date', table_name='conversation_analysis')

    # Drop tables
    op.drop_table('processing_log')
    op.drop_table('daily_aggregates')
    op.drop_table('conversation_analysis')