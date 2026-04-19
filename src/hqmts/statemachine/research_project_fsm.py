"""ResearchProject state machine (6-stage lifecycle).

States: created, exploring, hypothesizing, designing, executing, validating, reporting,
        completed, failed, canceled

Constraints:
- Terminal states: completed, failed, canceled
- Linear progression through 6 stages, with rollback allowed from validating → executing
- Any active stage can transition to canceled or failed
"""

from __future__ import annotations

from hqmts.core.enums import ResearchProjectStatus
from hqmts.statemachine.base import StateMachine

RESEARCH_PROJECT_TRANSITIONS: dict[ResearchProjectStatus, set[ResearchProjectStatus]] = {
    ResearchProjectStatus.CREATED: {
        ResearchProjectStatus.EXPLORING,
        ResearchProjectStatus.CANCELED,
    },
    ResearchProjectStatus.EXPLORING: {
        ResearchProjectStatus.HYPOTHESIZING,
        ResearchProjectStatus.CANCELED,
        ResearchProjectStatus.FAILED,
    },
    ResearchProjectStatus.HYPOTHESIZING: {
        ResearchProjectStatus.DESIGNING,
        ResearchProjectStatus.CANCELED,
        ResearchProjectStatus.FAILED,
    },
    ResearchProjectStatus.DESIGNING: {
        ResearchProjectStatus.EXECUTING,
        ResearchProjectStatus.CANCELED,
        ResearchProjectStatus.FAILED,
    },
    ResearchProjectStatus.EXECUTING: {
        ResearchProjectStatus.VALIDATING,
        ResearchProjectStatus.CANCELED,
        ResearchProjectStatus.FAILED,
    },
    ResearchProjectStatus.VALIDATING: {
        ResearchProjectStatus.REPORTING,
        ResearchProjectStatus.EXECUTING,  # Rollback: re-execute after validation failure
        ResearchProjectStatus.CANCELED,
        ResearchProjectStatus.FAILED,
    },
    ResearchProjectStatus.REPORTING: {
        ResearchProjectStatus.COMPLETED,
        ResearchProjectStatus.CANCELED,
        ResearchProjectStatus.FAILED,
    },
    ResearchProjectStatus.COMPLETED: set(),  # Terminal
    ResearchProjectStatus.FAILED: set(),  # Terminal
    ResearchProjectStatus.CANCELED: set(),  # Terminal
}

RESEARCH_PROJECT_TERMINAL_STATES: set[ResearchProjectStatus] = {
    ResearchProjectStatus.COMPLETED,
    ResearchProjectStatus.FAILED,
    ResearchProjectStatus.CANCELED,
}

research_project_fsm = StateMachine[ResearchProjectStatus](
    entity_type="ResearchProject",
    transitions=RESEARCH_PROJECT_TRANSITIONS,
    terminal_states=RESEARCH_PROJECT_TERMINAL_STATES,
)
