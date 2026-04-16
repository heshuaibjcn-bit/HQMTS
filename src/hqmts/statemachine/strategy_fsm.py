"""Strategy instance state machine (SAD 15.3).

States: draft, approved, paper_running, live_preparing, pause_open,
        live_running, close_only, stopped, failed, recovering

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
    StrategyStatus.DRAFT: {StrategyStatus.APPROVED, StrategyStatus.STOPPED},
    StrategyStatus.APPROVED: {
        StrategyStatus.PAPER_RUNNING,
        StrategyStatus.LIVE_PREPARING,
        StrategyStatus.STOPPED,
    },
    StrategyStatus.PAPER_RUNNING: {
        StrategyStatus.APPROVED,
        StrategyStatus.STOPPED,
        StrategyStatus.FAILED,
    },
    StrategyStatus.LIVE_PREPARING: {
        StrategyStatus.PAUSE_OPEN,
        StrategyStatus.LIVE_RUNNING,
        StrategyStatus.FAILED,
        StrategyStatus.STOPPED,
    },
    StrategyStatus.PAUSE_OPEN: {
        StrategyStatus.LIVE_RUNNING,
        StrategyStatus.CLOSE_ONLY,
        StrategyStatus.STOPPED,
        StrategyStatus.RECOVERING,
    },
    StrategyStatus.LIVE_RUNNING: {
        StrategyStatus.PAUSE_OPEN,
        StrategyStatus.CLOSE_ONLY,
        StrategyStatus.RECOVERING,
        StrategyStatus.FAILED,
        StrategyStatus.STOPPED,
    },
    StrategyStatus.CLOSE_ONLY: {
        StrategyStatus.PAUSE_OPEN,
        StrategyStatus.STOPPED,
        StrategyStatus.RECOVERING,
    },
    StrategyStatus.STOPPED: {StrategyStatus.APPROVED},
    StrategyStatus.FAILED: {StrategyStatus.RECOVERING, StrategyStatus.STOPPED},
    StrategyStatus.RECOVERING: {
        StrategyStatus.PAUSE_OPEN,
        StrategyStatus.CLOSE_ONLY,
        StrategyStatus.FAILED,
    },
}

STRATEGY_TERMINAL_STATES: set[StrategyStatus] = set()  # No terminal states

strategy_fsm = StateMachine[StrategyStatus](
    entity_type="StrategyInstance",
    transitions=STRATEGY_TRANSITIONS,
    terminal_states=STRATEGY_TERMINAL_STATES,
)
