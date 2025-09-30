"""Add chat_date column to chat_analysis table

This migration adds the chat_date column to track when the chat actually occurred,
separate from when it was processed. This fixes the logical error where time savings
were attributed to the processing date instead of when the chat actually happened.

Revision ID: cf003_add_chat_date
Revises: cf002_analytics_tables
Create Date: 2025-09-29

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'cf003_add_chat_date'
down_revision: Union[str, None] = 'cf002_analytics_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    """Add chat_date column and backfill with data from processed_at."""

    # Add the new chat_date column as nullable first
    op.add_column('chat_analysis',
                  sa.Column('chat_date', sa.Date(), nullable=True))

    # Backfill existing records with chat_date = DATE(processed_at)
    # This preserves existing data during the migration
    op.execute(text("""
        UPDATE chat_analysis
        SET chat_date = DATE(processed_at)
        WHERE chat_date IS NULL
    """))

    # Now make the column NOT NULL
    op.alter_column('chat_analysis', 'chat_date', nullable=False)

    # Add index for better query performance
    op.create_index('idx_chat_analysis_chat_date', 'chat_analysis', ['chat_date'])


def downgrade():
    """Remove chat_date column."""

    # Drop index first
    op.drop_index('idx_chat_analysis_chat_date', table_name='chat_analysis')

    # Drop the column
    op.drop_column('chat_analysis', 'chat_date')