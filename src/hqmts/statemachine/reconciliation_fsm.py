"""Reconciliation state machine (SAD 15.4).

States: initialized, comparing, matched, mismatched, adjusting,
        completed, failed, canceled, escalated

Terminal states: completed, failed, canceled, escalated

Agent role:
- Can analyze mismatch
- Can generate correction proposal
- Cannot directly execute correction
"""

from __future__ import annotations

from hqmts.core.enums import ReconciliationStatus
from hqmts.statemachine.base import StateMachine

RECONCILIATION_TRANSITIONS: dict[ReconciliationStatus, set[ReconciliationStatus]] = {
    ReconciliationStatus.INITIALIZED: {
        ReconciliationStatus.COMPARING,
        ReconciliationStatus.CANCELED,
    },
    ReconciliationStatus.COMPARING: {
        ReconciliationStatus.MATCHED,
        ReconciliationStatus.MISMATCHED,
        ReconciliationStatus.FAILED,
    },
    ReconciliationStatus.MATCHED: {ReconciliationStatus.COMPLETED},
    ReconciliationStatus.MISMATCHED: {
        ReconciliationStatus.ADJUSTING,
        ReconciliationStatus.ESCALATED,
    },
    ReconciliationStatus.ADJUSTING: {
        ReconciliationStatus.COMPLETED,
        ReconciliationStatus.FAILED,
    },
    ReconciliationStatus.COMPLETED: set(),  # Terminal
    ReconciliationStatus.FAILED: set(),  # Terminal
    ReconciliationStatus.CANCELED: set(),  # Terminal
    ReconciliationStatus.ESCALATED: set(),  # Terminal
}

RECONCILIATION_TERMINAL_STATES: set[ReconciliationStatus] = {
    ReconciliationStatus.COMPLETED,
    ReconciliationStatus.FAILED,
    ReconciliationStatus.CANCELED,
    ReconciliationStatus.ESCALATED,
}

reconciliation_fsm = StateMachine[ReconciliationStatus](
    entity_type="Reconciliation",
    transitions=RECONCILIATION_TRANSITIONS,
    terminal_states=RECONCILIATION_TERMINAL_STATES,
)
