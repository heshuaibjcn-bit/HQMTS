"""Tests for Alembic migration correctness.

Verifies that the migration up/down cycle is idempotent and that
the migration produces the same schema as Base.metadata.create_all.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

from hqmts.db.base import Base

# Force import all models so Base.metadata knows about them
from hqmts.db.models import (  # noqa: F401
    account,
    agent_proposal,
    agent_task,
    approval_request,
    audit,
    bar,
    chat,
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
    risk,
    signal,
    strategy,
    tool_invocation,
    trade,
    user,
    alert,
    version,
)

from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext


@pytest.fixture
def alembic_cfg(tmp_path):
    """Alembic config pointing at a temporary SQLite DB via aiosqlite."""
    db_path = tmp_path / "test.db"
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    cfg.set_main_option("prepend_sys_path", ".")
    return cfg


def _get_table_names(engine, include_alembic=False):
    insp = inspect(engine)
    tables = sorted(insp.get_table_names())
    if not include_alembic:
        tables = [t for t in tables if t != "alembic_version"]
    return tables


def _get_column_names(engine, table_name):
    insp = inspect(engine)
    return sorted(c["name"] for c in insp.get_columns(table_name))


class TestAlembicMigration:
    """Verify migration correctness."""

    def test_upgrade_creates_all_tables(self, alembic_cfg, tmp_path):
        """upgrade head should create all 25 tables."""
        command.upgrade(alembic_cfg, "head")

        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}")
        tables = _get_table_names(engine)
        engine.dispose()

        assert len(tables) == 32
        # Spot-check key tables
        assert "orders" in tables
        assert "signals" in tables
        assert "audit_events" in tables
        assert "recovery_sessions" in tables

    def test_downgrade_removes_all_tables(self, alembic_cfg, tmp_path):
        """downgrade base should remove all tables."""
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "base")

        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}")
        tables = _get_table_names(engine)
        engine.dispose()

        # Only alembic_version tracking table should remain
        assert len(tables) == 0

    def test_up_down_up_idempotent(self, alembic_cfg, tmp_path):
        """up -> down -> up should produce the same schema."""
        db_path = tmp_path / "test.db"

        # First up
        command.upgrade(alembic_cfg, "head")
        engine = create_engine(f"sqlite:///{db_path}")
        tables_first = _get_table_names(engine)
        engine.dispose()

        # Down
        command.downgrade(alembic_cfg, "base")

        # Second up
        command.upgrade(alembic_cfg, "head")
        engine = create_engine(f"sqlite:///{db_path}")
        tables_second = _get_table_names(engine)
        engine.dispose()

        assert tables_first == tables_second

    def test_migration_matches_orm_tables(self, alembic_cfg, tmp_path):
        """Migration should create the same tables as Base.metadata.create_all."""
        # Tables from migration
        command.upgrade(alembic_cfg, "head")
        db_path = tmp_path / "test.db"
        engine_mig = create_engine(f"sqlite:///{db_path}")
        mig_tables = _get_table_names(engine_mig)
        engine_mig.dispose()

        # Tables from ORM
        engine_orm = create_engine("sqlite://")
        Base.metadata.create_all(engine_orm)
        orm_tables = _get_table_names(engine_orm)
        engine_orm.dispose()

        assert mig_tables == orm_tables

    def test_key_table_columns_match(self, alembic_cfg, tmp_path):
        """Key tables should have matching columns between migration and ORM."""
        # Tables from migration
        command.upgrade(alembic_cfg, "head")
        db_path = tmp_path / "test.db"
        engine_mig = create_engine(f"sqlite:///{db_path}")

        # Tables from ORM
        engine_orm = create_engine("sqlite://")
        Base.metadata.create_all(engine_orm)

        # Compare columns for critical tables
        for table in ["orders", "signals", "audit_events", "recovery_sessions",
                       "agent_tasks", "agent_proposals", "cash_reservations"]:
            mig_cols = _get_column_names(engine_mig, table)
            orm_cols = _get_column_names(engine_orm, table)
            assert mig_cols == orm_cols, (
                f"Column mismatch for {table}: "
                f"migration={mig_cols}, orm={orm_cols}"
            )

        engine_mig.dispose()
        engine_orm.dispose()

    def test_single_revision_exists(self):
        """There should be migration revisions chained correctly."""
        cfg = Config()
        cfg.set_main_option("script_location", "alembic")
        script = ScriptDirectory.from_config(cfg)
        revisions = list(script.walk_revisions())
        assert len(revisions) == 4
        assert revisions[0].revision == "004"
        assert revisions[1].revision == "003"
        assert revisions[2].revision == "002"
        assert revisions[3].revision == "001"
