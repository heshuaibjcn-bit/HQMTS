"""Strategy instance state machine (SAD 15.3).

States: draft, backtest_ready, validation_ready, paper_running,
        live_running, pause_open, close_only, stopped, paused, archived

Terminal states: archived

Constraints:
- Entering live_running requires approval or explicit rule authorization
- Agent cannot automatically restore strategy to live_running
- Agent can create recovery or go-live proposals
"""

from __future__ import annotations

from hqmts.core.enums import StrategyStatus
from hqmts.statemachine.base import StateMachine

# Transition table from SAD 15.3
STRATEGY_TRANSITIONS: dict[StrategyStatus, set[StrategyStatus]] = {
    StrategyStatus.DRAFT: {StrategyStatus.BACKTEST_READY, StrategyStatus.ARCHIVED},
    StrategyStatus.BACKTEST_READY: {
        StrategyStatus.VALIDATION_READY,
        StrategyStatus.DRAFT,
        StrategyStatus.ARCHIVED,
    },
    StrategyStatus.VALIDATION_READY: {
        StrategyStatus.PAPER_RUNNING,
        StrategyStatus.BACKTEST_READY,
        StrategyStatus.ARCHIVED,
    },
    StrategyStatus.PAPER_RUNNING: {
        StrategyStatus.LIVE_RUNNING,
        StrategyStatus.VALIDATION_READY,
        StrategyStatus.PAUSED,
        StrategyStatus.ARCHIVED,
    },
    StrategyStatus.LIVE_RUNNING: {
        StrategyStatus.PAUSE_OPEN,
        StrategyStatus.CLOSE_ONLY,
        StrategyStatus.STOPPED,
        StrategyStatus.ARCHIVED,
    },
    StrategyStatus.PAUSE_OPEN: {
        StrategyStatus.LIVE_RUNNING,
        StrategyStatus.CLOSE_ONLY,
        StrategyStatus.STOPPED,
    },
    StrategyStatus.CLOSE_ONLY: {
        StrategyStatus.PAUSE_OPEN,
        StrategyStatus.STOPPED,
    },
    StrategyStatus.STOPPED: {StrategyStatus.DRAFT, StrategyStatus.ARCHIVED},
    StrategyStatus.PAUSED: {StrategyStatus.PAPER_RUNNING, StrategyStatus.STOPPED},
    StrategyStatus.ARCHIVED: set(),  # Terminal
}

STRATEGY_TERMINAL_STATES: set[StrategyStatus] = {StrategyStatus.ARCHIVED}

strategy_fsm = StateMachine[StrategyStatus](
    entity_type="StrategyInstance",
    transitions=STRATEGY_TRANSITIONS,
    terminal_states=STRATEGY_TERMINAL_STATES,
)