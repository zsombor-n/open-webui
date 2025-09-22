"""Initial cogniforce analytics tables

Revision ID: cf001_initial
Revises:
Create Date: 2025-01-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from open_webui.internal.db import JSONField

# revision identifiers, used by Alembic.
revision: str = 'cf001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create conversation_insights table
    op.create_table(
        'conversation_insights',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('message_count', sa.Integer(), default=0),
        sa.Column('avg_response_time', sa.Float(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('topics', JSONField(), nullable=True),
        sa.Column('insights_metadata', JSONField(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create user_engagement table
    op.create_table(
        'user_engagement',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('daily_active_days', sa.Integer(), default=0),
        sa.Column('total_conversations', sa.Integer(), default=0),
        sa.Column('total_messages', sa.Integer(), default=0),
        sa.Column('avg_session_duration', sa.Float(), nullable=True),
        sa.Column('last_activity_at', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for better performance
    op.create_index('idx_conversation_insights_user_id', 'conversation_insights', ['user_id'])
    op.create_index('idx_conversation_insights_conversation_id', 'conversation_insights', ['conversation_id'])
    op.create_index('idx_user_engagement_user_id', 'user_engagement', ['user_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_user_engagement_user_id', table_name='user_engagement')
    op.drop_index('idx_conversation_insights_conversation_id', table_name='conversation_insights')
    op.drop_index('idx_conversation_insights_user_id', table_name='conversation_insights')

    # Drop tables
    op.drop_table('user_engagement')
    op.drop_table('conversation_insights')