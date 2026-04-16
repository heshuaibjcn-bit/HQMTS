"""Generic state machine framework.

Provides a type-safe, immutable state machine with:
- Transition table validation
- Terminal state detection
- Audit hook points
- Illegal transition rejection
"""

from __future__ import annotations

from typing import Generic, TypeVar

from hqmts.core.exceptions import IllegalTransitionError, TerminalStateError

StateType = TypeVar("StateType", bound=str)


class StateMachine(Generic[StateType]):
    """Generic finite state machine.

    Usage:
        transitions = {
            "draft": {"approved", "stopped"},
            "approved": {"paper_running", "stopped"},
            "stopped": set(),  # terminal
        }
        terminal_states = {"stopped", "rejected"}
        fsm = StateMachine("strategy", transitions, terminal_states)
        new_state = fsm.transition("draft", "approved")  # "approved"
    """

    def __init__(
        self,
        entity_type: str,
        transitions: dict[StateType, set[StateType]],
        terminal_states: set[StateType],
    ) -> None:
        self._entity_type = entity_type
        self._transitions = transitions
        self._terminal_states = terminal_states
        self._validate_definitions()

    def _validate_definitions(self) -> None:
        """Validate transition table consistency."""
        for state, targets in self._transitions.items():
            for target in targets:
                if target not in self._transitions:
                    msg = (
                        f"[{self._entity_type}] Transition target '{target}' "
                        f"from '{state}' not defined in transition table"
                    )
                    raise ValueError(msg)

    @property
    def entity_type(self) -> str:
        return self._entity_type

    @property
    def terminal_states(self) -> frozenset[StateType]:
        return frozenset(self._terminal_states)

    def can_transition(self, current: StateType, target: StateType) -> bool:
        """Check if a transition is valid."""
        if current in self._terminal_states:
            return False
        allowed = self._transitions.get(current, set())
        return target in allowed

    def valid_transitions(self, current: StateType) -> list[StateType]:
        """Return list of valid target states from current state."""
        if current in self._terminal_states:
            return []
        return sorted(self._transitions.get(current, set()))

    def transition(self, current: StateType, target: StateType) -> StateType:
        """Execute a state transition.

        Args:
            current: Current state.
            target: Target state.

        Returns:
            The new state (same as target).

        Raises:
            TerminalStateError: If current state is terminal.
            IllegalTransitionError: If transition is not allowed.
        """
        if current in self._terminal_states:
            raise TerminalStateError(str(current), self._entity_type)

        allowed = self._transitions.get(current, set())
        if target not in allowed:
            raise IllegalTransitionError(str(current), str(target), self._entity_type)

        return target

    def is_terminal(self, state: StateType) -> bool:
        """Check if a state is terminal."""
        return state in self._terminal_states

    def get_all_states(self) -> list[StateType]:
        """Return all defined states."""
        return sorted(self._transitions.keys())
