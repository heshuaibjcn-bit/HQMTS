"""Reconciliation state machine (SAD 15.4).

States: pending, running, matched, mismatch_detected, corrected,
        escalated, closed

Agent role:
- Can analyze mismatch
- Can generate correction proposal
- Cannot directly execute correction
"""

from __future__ import annotations

from hqmts.core.enums import ReconciliationStatus
from hqmts.statemachine.base import StateMachine

RECONCILIATION_TRANSITIONS: dict[ReconciliationStatus, set[ReconciliationStatus]] = {
    ReconciliationStatus.PENDING: {ReconciliationStatus.RUNNING, ReconciliationStatus.CLOSED},
    ReconciliationStatus.RUNNING: {
        ReconciliationStatus.MATCHED,
        ReconciliationStatus.MISMATCH_DETECTED,
        ReconciliationStatus.ESCALATED,
        ReconciliationStatus.CLOSED,
    },
    ReconciliationStatus.MATCHED: {ReconciliationStatus.CLOSED},
    ReconciliationStatus.MISMATCH_DETECTED: {
        ReconciliationStatus.CORRECTED,
        ReconciliationStatus.ESCALATED,
        ReconciliationStatus.CLOSED,
    },
    ReconciliationStatus.CORRECTED: {ReconciliationStatus.CLOSED},
    ReconciliationStatus.ESCALATED: {
        ReconciliationStatus.MISMATCH_DETECTED,
        ReconciliationStatus.CORRECTED,
        ReconciliationStatus.CLOSED,
    },
    ReconciliationStatus.CLOSED: set(),  # Terminal
}

RECONCILIATION_TERMINAL_STATES: set[ReconciliationStatus] = {
    ReconciliationStatus.CLOSED,
}

reconciliation_fsm = StateMachine[ReconciliationStatus](
    entity_type="Reconciliation",
    transitions=RECONCILIATION_TRANSITIONS,
    terminal_states=RECONCILIATION_TERMINAL_STATES,
)
