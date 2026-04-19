"""Alembic environment configuration for async migrations."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from hqmts.db.base import Base
from hqmts.infra.config import load_settings

# Import all models so Alembic can detect them
from hqmts.db.models import (  # noqa: F401
    account,
    agent_task,
    agent_proposal,
    approval_request,
    audit,
    bar,
    controlled_execution,
    decision,
    execution,
    external_event,
    feature,
    instrument,
    order,
    position,
    reconciliation,
    recovery,
    reservation,
    research_cycle,
    risk,
    signal,
    strategy,
    tool_invocation,
    trade,
    version,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    import os
    # If HQMTS_ENV is set, always use the matching config file
    env = os.environ.get("HQMTS_ENV")
    if env:
        settings = load_settings(env)
        return settings.database.url
    # Otherwise prefer the URL set in alembic.ini
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url:
        return ini_url
    settings = load_settings()
    return settings.database.url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
