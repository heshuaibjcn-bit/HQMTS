"""AgentTask state machine (SAD 15.6).

States: created, planning, running, waiting_tool, completed, failed, timeout, canceled, escalated

Constraints:
- Terminal states: completed, failed, canceled, escalated
- Escalation is reachable from timeout or running
"""

from __future__ import annotations

from hqmts.core.enums import AgentTaskStatus
from hqmts.statemachine.base import StateMachine

AGENT_TASK_TRANSITIONS: dict[AgentTaskStatus, set[AgentTaskStatus]] = {
    AgentTaskStatus.CREATED: {AgentTaskStatus.PLANNING, AgentTaskStatus.CANCELED},
    AgentTaskStatus.PLANNING: {AgentTaskStatus.RUNNING, AgentTaskStatus.FAILED, AgentTaskStatus.CANCELED},
    AgentTaskStatus.RUNNING: {
        AgentTaskStatus.WAITING_TOOL,
        AgentTaskStatus.COMPLETED,
        AgentTaskStatus.FAILED,
        AgentTaskStatus.TIMEOUT,
        AgentTaskStatus.ESCALATED,
    },
    AgentTaskStatus.WAITING_TOOL: {
        AgentTaskStatus.RUNNING,
        AgentTaskStatus.FAILED,
        AgentTaskStatus.TIMEOUT,
        AgentTaskStatus.CANCELED,
    },
    AgentTaskStatus.COMPLETED: set(),  # Terminal
    AgentTaskStatus.FAILED: set(),  # Terminal
    AgentTaskStatus.TIMEOUT: {AgentTaskStatus.ESCALATED},
    AgentTaskStatus.CANCELED: set(),  # Terminal
    AgentTaskStatus.ESCALATED: set(),  # Terminal
}

AGENT_TASK_TERMINAL_STATES: set[AgentTaskStatus] = {
    AgentTaskStatus.COMPLETED,
    AgentTaskStatus.FAILED,
    AgentTaskStatus.CANCELED,
    AgentTaskStatus.ESCALATED,
}

agent_task_fsm = StateMachine[AgentTaskStatus](
    entity_type="AgentTask",
    transitions=AGENT_TASK_TRANSITIONS,
    terminal_states=AGENT_TASK_TERMINAL_STATES,
)
