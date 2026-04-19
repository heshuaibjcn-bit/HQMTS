"""Controlled execution state machine (SAD 7.10).

States: pending, executing, completed, failed, expired

Terminal states: completed, failed, expired
"""

from __future__ import annotations

from hqmts.core.enums import ExecutionStatus
from hqmts.statemachine.base import StateMachine

CONTROLLED_EXECUTION_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.PENDING: {ExecutionStatus.EXECUTING, ExecutionStatus.EXPIRED},
    ExecutionStatus.EXECUTING: {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED},
    ExecutionStatus.COMPLETED: set(),  # Terminal
    ExecutionStatus.FAILED: set(),  # Terminal
    ExecutionStatus.EXPIRED: set(),  # Terminal
}

CONTROLLED_EXECUTION_TERMINAL_STATES: set[ExecutionStatus] = {
    ExecutionStatus.COMPLETED,
    ExecutionStatus.FAILED,
    ExecutionStatus.EXPIRED,
}

controlled_execution_fsm = StateMachine[ExecutionStatus](
    entity_type="ControlledExecution",
    transitions=CONTROLLED_EXECUTION_TRANSITIONS,
    terminal_states=CONTROLLED_EXECUTION_TERMINAL_STATES,
)
