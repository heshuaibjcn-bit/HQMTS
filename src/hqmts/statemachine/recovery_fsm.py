"""Recovery session state machine (SAD 15.5).

States: created, diagnosing, recovering, verifying,
        completed, failed, canceled

Terminal states: completed, failed, canceled

Agent role:
- Can generate recovery suggestions
- Can summarize exception chain
- Can assist with recovery report generation
- Cannot bypass verifying
"""

from __future__ import annotations

from hqmts.core.enums import RecoveryStatus
from hqmts.statemachine.base import StateMachine

RECOVERY_TRANSITIONS: dict[RecoveryStatus, set[RecoveryStatus]] = {
    RecoveryStatus.CREATED: {
        RecoveryStatus.DIAGNOSING,
        RecoveryStatus.CANCELED,
    },
    RecoveryStatus.DIAGNOSING: {
        RecoveryStatus.RECOVERING,
        RecoveryStatus.FAILED,
        RecoveryStatus.CANCELED,
    },
    RecoveryStatus.RECOVERING: {
        RecoveryStatus.VERIFYING,
        RecoveryStatus.FAILED,
    },
    RecoveryStatus.VERIFYING: {
        RecoveryStatus.COMPLETED,
        RecoveryStatus.RECOVERING,
        RecoveryStatus.FAILED,
    },
    RecoveryStatus.COMPLETED: set(),  # Terminal
    RecoveryStatus.FAILED: set(),  # Terminal
    RecoveryStatus.CANCELED: set(),  # Terminal
}

RECOVERY_TERMINAL_STATES: set[RecoveryStatus] = {
    RecoveryStatus.COMPLETED,
    RecoveryStatus.FAILED,
    RecoveryStatus.CANCELED,
}

recovery_fsm = StateMachine[RecoveryStatus](
    entity_type="Recovery",
    transitions=RECOVERY_TRANSITIONS,
    terminal_states=RECOVERY_TERMINAL_STATES,
)
