"""Start backend with SQLite test database for browser QA."""

import sys
import os

# Monkey-patch create_engine to use SQLite
import hqmts.db.connection as _db_conn
from sqlalchemy.ext.asyncio import create_async_engine

_orig_create_engine = _db_conn.create_engine

def _sqlite_engine(config):
    db_path = os.path.join(os.path.dirname(__file__), "test_qa.db")
    return create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )

_db_conn.create_engine = _sqlite_engine

# Patch Redis to no-op
import hqmts.infra.config as _cfg
_cfg.RedisConfig.url = "redis://localhost:6379/0"

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "hqmts.api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
