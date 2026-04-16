"""Tests for Order state machine."""

import pytest

from hqmts.core.enums import OrderStatus
from hqmts.core.exceptions import IllegalTransitionError, TerminalStateError
from hqmts.statemachine.order_fsm import order_fsm


class TestOrderFSM:
    """Tests based on SAD 15.1 Order state machine."""

    def test_initial_transition(self):
        result = order_fsm.transition(OrderStatus.CREATED, OrderStatus.SUBMITTING)
        assert result == OrderStatus.SUBMITTING

    def test_created_to_submitting(self):
        assert order_fsm.can_transition(OrderStatus.CREATED, OrderStatus.SUBMITTING)

    def test_created_to_rejected(self):
        assert order_fsm.can_transition(OrderStatus.CREATED, OrderStatus.REJECTED)

    def test_created_to_expired(self):
        assert order_fsm.can_transition(OrderStatus.CREATED, OrderStatus.EXPIRED)

    def test_created_cannot_go_to_filled(self):
        assert not order_fsm.can_transition(OrderStatus.CREATED, OrderStatus.FILLED)

    def test_submitting_to_submitted(self):
        assert order_fsm.can_transition(OrderStatus.SUBMITTING, OrderStatus.SUBMITTED)

    def test_submitting_to_uncertain(self):
        assert order_fsm.can_transition(OrderStatus.SUBMITTING, OrderStatus.UNCERTAIN)

    def test_submitted_to_accepted(self):
        assert order_fsm.can_transition(OrderStatus.SUBMITTED, OrderStatus.ACCEPTED)

    def test_submitted_to_partially_filled(self):
        assert order_fsm.can_transition(OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)

    def test_submitted_to_filled(self):
        assert order_fsm.can_transition(OrderStatus.SUBMITTED, OrderStatus.FILLED)

    def test_partially_filled_self_loop(self):
        assert order_fsm.can_transition(
            OrderStatus.PARTIALLY_FILLED, OrderStatus.PARTIALLY_FILLED
        )

    def test_partially_filled_to_filled(self):
        assert order_fsm.can_transition(OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED)

    def test_uncertain_to_accepted(self):
        assert order_fsm.can_transition(OrderStatus.UNCERTAIN, OrderStatus.ACCEPTED)

    def test_uncertain_to_canceled(self):
        assert order_fsm.can_transition(OrderStatus.UNCERTAIN, OrderStatus.CANCELED)

    def test_uncertain_to_rejected(self):
        assert order_fsm.can_transition(OrderStatus.UNCERTAIN, OrderStatus.REJECTED)

    # Terminal states
    def test_filled_is_terminal(self):
        assert order_fsm.is_terminal(OrderStatus.FILLED)

    def test_canceled_is_terminal(self):
        assert order_fsm.is_terminal(OrderStatus.CANCELED)

    def test_rejected_is_terminal(self):
        assert order_fsm.is_terminal(OrderStatus.REJECTED)

    def test_expired_is_terminal(self):
        assert order_fsm.is_terminal(OrderStatus.EXPIRED)

    def test_created_is_not_terminal(self):
        assert not order_fsm.is_terminal(OrderStatus.CREATED)

    # Illegal transitions
    def test_illegal_transition_raises(self):
        with pytest.raises(IllegalTransitionError):
            order_fsm.transition(OrderStatus.CREATED, OrderStatus.FILLED)

    def test_terminal_transition_raises(self):
        with pytest.raises(TerminalStateError):
            order_fsm.transition(OrderStatus.FILLED, OrderStatus.CREATED)

    # Valid transitions listing
    def test_valid_transitions_from_created(self):
        valid = order_fsm.valid_transitions(OrderStatus.CREATED)
        assert OrderStatus.SUBMITTING in valid
        assert OrderStatus.REJECTED in valid
        assert OrderStatus.EXPIRED in valid
        assert len(valid) == 3

    def test_valid_transitions_from_terminal(self):
        valid = order_fsm.valid_transitions(OrderStatus.FILLED)
        assert len(valid) == 0

    def test_all_states_defined(self):
        all_states = order_fsm.get_all_states()
        assert len(all_states) == 11

    def test_full_happy_path(self):
        """Test the happy path: created → submitting → submitted → filled."""
        state = OrderStatus.CREATED
        state = order_fsm.transition(state, OrderStatus.SUBMITTING)
        assert state == OrderStatus.SUBMITTING
        state = order_fsm.transition(state, OrderStatus.SUBMITTED)
        assert state == OrderStatus.SUBMITTED
        state = order_fsm.transition(state, OrderStatus.FILLED)
        assert state == OrderStatus.FILLED
        assert order_fsm.is_terminal(state)

    def test_uncertain_recovery_path(self):
        """Test uncertain → accepted → partially_filled → filled."""
        state = OrderStatus.UNCERTAIN
        state = order_fsm.transition(state, OrderStatus.ACCEPTED)
        state = order_fsm.transition(state, OrderStatus.PARTIALLY_FILLED)
        state = order_fsm.transition(state, OrderStatus.FILLED)
        assert order_fsm.is_terminal(state)
