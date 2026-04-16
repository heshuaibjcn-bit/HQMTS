# HQMTS

Hermes Quant Minute Trading System. A-stock minute-level quantitative trading platform.

## Setup

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/unit/test_risk_rules.py -v
```

## Architecture

```
src/hqmts/
  core/       Enums, types, exceptions
  domain/     Pydantic models (no DB dependency)
  statemachine/  Order, Strategy, Reconciliation, Recovery FSMs
  db/         SQLAlchemy ORM models + async repositories
  risk/       5-layer risk engine (Market > Account > Strategy > Instrument > Order)
  execution/  Signal -> Intent -> Order pipeline
  reservation/ Cash reservation lifecycle
  agent/      Governance layer (Proposal -> Policy -> Approval -> Execution)
  api/        FastAPI REST endpoints
  infra/      Config, logging, Redis
```

Key design decisions:
- Domain models are pure Pydantic, no ORM dependency
- Agent governance enforces: agents cannot write core trading tables or call QMT directly
- Risk priority: force_flatten > reject > resize > delay > allow
- 4 state machines: Order (11 states), Strategy (10), Reconciliation (7), Recovery (8)

## Configuration

Environment configs in `configs/`:
- `base.yaml` — shared defaults
- `research.yaml` / `backtest.yaml` / `paper.yaml` / `live.yaml` — environment overrides

All config values can be overridden via environment variables (Pydantic Settings).

## Test Structure

```
tests/
  unit/       State machines, risk rules, final check, agent permission, rejection handling
  integration/  Order lifecycle, reservation flow, audit trail, governance chain
```

181 tests, all async via pytest-asyncio, using in-memory SQLite.

## API

```bash
uv run python scripts/run_dev.py
```

FastAPI endpoints: `/api/v1/instruments`, `/strategies`, `/signals`, `/orders`, `/risk`, `/audit`.
