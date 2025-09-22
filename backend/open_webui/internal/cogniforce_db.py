import os
import logging
from contextlib import contextmanager
from typing import Any, Optional
import subprocess
import sys
from pathlib import Path

from open_webui.env import (
    COGNIFORCE_DATABASE_URL,
    SRC_LOG_LEVELS,
    DATABASE_POOL_MAX_OVERFLOW,
    DATABASE_POOL_RECYCLE,
    DATABASE_POOL_SIZE,
    DATABASE_POOL_TIMEOUT,
    OPEN_WEBUI_DIR,
)
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.exc import OperationalError, ProgrammingError

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["DB"])

# Cogniforce Database Configuration
COGNIFORCE_SQLALCHEMY_DATABASE_URL = COGNIFORCE_DATABASE_URL

# Create Cogniforce Database Engine
if "sqlite" in COGNIFORCE_SQLALCHEMY_DATABASE_URL:
    cogniforce_engine = create_engine(
        COGNIFORCE_SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL or other databases
    if isinstance(DATABASE_POOL_SIZE, int):
        if DATABASE_POOL_SIZE > 0:
            cogniforce_engine = create_engine(
                COGNIFORCE_SQLALCHEMY_DATABASE_URL,
                pool_size=DATABASE_POOL_SIZE,
                max_overflow=DATABASE_POOL_MAX_OVERFLOW,
                pool_timeout=DATABASE_POOL_TIMEOUT,
                pool_recycle=DATABASE_POOL_RECYCLE,
                pool_pre_ping=True,
                poolclass=QueuePool,
            )
        else:
            cogniforce_engine = create_engine(
                COGNIFORCE_SQLALCHEMY_DATABASE_URL,
                pool_pre_ping=True,
                poolclass=NullPool
            )
    else:
        cogniforce_engine = create_engine(
            COGNIFORCE_SQLALCHEMY_DATABASE_URL,
            pool_pre_ping=True
        )

# Cogniforce Session Configuration
CogniforceSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=cogniforce_engine,
    expire_on_commit=False
)

# Cogniforce Metadata and Base
cogniforce_metadata_obj = MetaData()
CogniforceBase = declarative_base(metadata=cogniforce_metadata_obj)
CogniforceSession = scoped_session(CogniforceSessionLocal)

def get_cogniforce_session():
    """Get Cogniforce database session."""
    db = CogniforceSessionLocal()
    try:
        yield db
    finally:
        db.close()

get_cogniforce_db = contextmanager(get_cogniforce_session)


def create_cogniforce_database_if_not_exists():
    """Create the Cogniforce database if it doesn't exist (PostgreSQL only)."""
    if "postgresql://" not in COGNIFORCE_DATABASE_URL:
        # For SQLite, database file is created automatically
        return

    try:
        # Parse the database URL to get components
        from urllib.parse import urlparse
        parsed = urlparse(COGNIFORCE_DATABASE_URL)

        # Extract database name
        db_name = parsed.path.lstrip('/')

        # Create URL without database name for initial connection
        admin_url = f"{parsed.scheme}://{parsed.netloc}/postgres"

        # Connect to PostgreSQL server (default 'postgres' database)
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

        with admin_engine.connect() as conn:
            # Check if database exists
            result = conn.execute(text(
                "SELECT 1 FROM pg_database WHERE datname = :db_name"
            ), {"db_name": db_name})

            if not result.fetchone():
                # Create database
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                log.info(f"Created Cogniforce database: {db_name}")
            else:
                log.info(f"Cogniforce database already exists: {db_name}")

        admin_engine.dispose()

    except Exception as e:
        log.warning(f"Could not create Cogniforce database automatically: {e}")
        log.warning("Please create the database manually or check permissions")


def run_cogniforce_migrations():
    """Run Cogniforce database migrations."""
    try:
        # Get the path to the cogniforce alembic configuration
        alembic_config_path = OPEN_WEBUI_DIR / "cogniforce_alembic.ini"

        if not alembic_config_path.exists():
            log.warning("Cogniforce alembic configuration not found. Skipping migrations.")
            return

        # Change to the correct directory for alembic
        original_cwd = os.getcwd()
        os.chdir(OPEN_WEBUI_DIR)

        try:
            # Run alembic upgrade head for cogniforce database
            result = subprocess.run([
                sys.executable, "-m", "alembic",
                "-c", "cogniforce_alembic.ini",
                "upgrade", "head"
            ], capture_output=True, text=True, check=False)

            if result.returncode == 0:
                log.info("Cogniforce database migrations completed successfully")
            else:
                log.warning(f"Cogniforce migrations had issues: {result.stderr}")

        finally:
            os.chdir(original_cwd)

    except Exception as e:
        log.error(f"Failed to run Cogniforce migrations: {e}")


def initialize_cogniforce_database():
    """Initialize the Cogniforce database - create database and run migrations."""
    log.info("Initializing Cogniforce database...")

    # Step 1: Create database if it doesn't exist
    create_cogniforce_database_if_not_exists()

    # Step 2: Run migrations
    run_cogniforce_migrations()

    log.info("Cogniforce database initialization completed")


log.info(f"Cogniforce database configured: {COGNIFORCE_SQLALCHEMY_DATABASE_URL[:50]}...")