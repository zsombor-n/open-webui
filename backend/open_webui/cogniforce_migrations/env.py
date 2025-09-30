from logging.config import fileConfig

from alembic import context
from open_webui.internal.cogniforce_db import CogniforceBase
from open_webui.env import COGNIFORCE_DATABASE_URL

# Import all cogniforce models to ensure they're registered with the metadata
from open_webui.cogniforce_models import analytics, analytics_tables
from sqlalchemy import engine_from_config, pool, create_engine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = CogniforceBase.metadata

# Set the database URL from environment
COGNIFORCE_DB_URL = COGNIFORCE_DATABASE_URL

if COGNIFORCE_DB_URL:
    config.set_main_option("sqlalchemy.url", COGNIFORCE_DB_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()