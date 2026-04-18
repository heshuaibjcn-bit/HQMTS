# Changelog

All notable changes to this project will be documented in this file.

## [1.5.0.0] - 2026-04-18

### Added
- **Web dashboard and AI chat frontend** (React 19 + Vite 8 + TypeScript + Tailwind CSS v4)
  - 10 pages: Overview, Positions, Orders, Risk, Strategies, Signals, Backtest, Audit, Monitoring, Chat
  - JWT auth with access/refresh token flow and session persistence
  - WebSocket real-time data with auto-reconnect and ping/pong heartbeat
  - SSE-based AI chat with streaming responses and slash commands
  - Kill switch and force flatten controls with confirmation guards
  - Environment switcher (Research/Backtest/Paper/Live) with confirmation for Live
  - Error boundaries, toast notifications, and WS status banner
- **Backend JWT authentication system** (login, refresh, me, logout endpoints)
- **WebSocket bridge** connecting PipelineBus to browser clients with auth, heartbeat, and message buffering
- **AI chat backend** with SSE streaming, session management, and LLM adapter layer (OpenAI + Ollama)
- **Alert system** with acknowledgment and REST endpoints
- **Account summary API** aggregating positions, orders, and P&L
- **Live environment orchestrator** with 14-step startup sequence (SAD 22.1)
- **Force flatten service** for risk-initiated liquidation (SAD 18.3)
- **Paper-to-live admission service** with strategy readiness checks (SAD 25)
- **Strategy sandbox** for runtime strategy restrictions (SAD 13.2/13.3)
- **Correction handler** for reconciliation mismatches (SAD 10.4)
- **Metrics collector** pipeline wiring AlertService to real metrics (SAD 28)
- **QMT health monitor** for external broker connection status
- **Typed IDs and enums** for domain model type safety

### Changed
- Aligned 6 enums and 5 FSMs to SAD V1.3 state tables
- Aligned domain models, ORM, repositories, and services to SAD V1.3
- Added serialization_key() to domain objects, switched datetime.now() to now_shanghai()
- Rewrote FSM, service, and integration tests for SAD V1.3 alignment

### Fixed
- Vite proxy collision with SPA routes (ISSUE-001) — bypass function for browser navigations
- Fail-safe defaults, FSM enforcement, and audit logging gaps (P0/P1 adversarial audit)
- Safety pipeline, reservation lock, consume(), and policy checks (P2 adversarial audit)
- External event actions, QMT health, stale price, and auto-approve guard (P3 adversarial audit)
- Decision validation, alert levels, tool registry, and shared side mapping (M-level audit)
- Typed ProposalStatus replacing loose approval_status string
- Datetime timezone safety in PaperOrder and active strategy query completeness
- 3 HIGH issues: datetime TZ handling, reject handler, auth comment
