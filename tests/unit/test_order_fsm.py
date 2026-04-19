"""Tests for Order state machine (SAD 15.1)."""

import pytest

from hqmts.core.enums import OrderStatus
from hqmts.core.exceptions import IllegalTransitionError, TerminalStateError
from hqmts.statemachine.order_fsm import order_fsm


class TestOrderFSM:
    """Tests based on SAD 15.1 Order state machine."""

    # Basic transitions from CREATED
    def test_created_to_pending_submit(self):
        assert order_fsm.can_transition(OrderStatus.CREATED, OrderStatus.PENDING_SUBMIT)

    def test_created_to_canceled(self):
        assert order_fsm.can_transition(OrderStatus.CREATED, OrderStatus.CANCELED)

    def test_created_cannot_go_to_filled(self):
        assert not order_fsm.can_transition(OrderStatus.CREATED, OrderStatus.FILLED)

    # PENDING_SUBMIT transitions
    def test_pending_submit_to_submitted(self):
        assert order_fsm.can_transition(OrderStatus.PENDING_SUBMIT, OrderStatus.SUBMITTED)

    def test_pending_submit_to_canceled(self):
        assert order_fsm.can_transition(OrderStatus.PENDING_SUBMIT, OrderStatus.CANCELED)

    # SUBMITTED transitions
    def test_submitted_to_accepted(self):
        assert order_fsm.can_transition(OrderStatus.SUBMITTED, OrderStatus.ACCEPTED)

    def test_submitted_to_rejected(self):
        assert order_fsm.can_transition(OrderStatus.SUBMITTED, OrderStatus.REJECTED)

    def test_submitted_to_canceled(self):
        assert order_fsm.can_transition(OrderStatus.SUBMITTED, OrderStatus.CANCELED)

    # ACCEPTED transitions
    def test_accepted_to_partial_filled(self):
        assert order_fsm.can_transition(OrderStatus.ACCEPTED, OrderStatus.PARTIAL_FILLED)

    def test_accepted_to_filled(self):
        assert order_fsm.can_transition(OrderStatus.ACCEPTED, OrderStatus.FILLED)

    def test_accepted_to_canceled(self):
        assert order_fsm.can_transition(OrderStatus.ACCEPTED, OrderStatus.CANCELED)

    # PARTIAL_FILLED transitions
    def test_partial_filled_self_loop(self):
        assert order_fsm.can_transition(OrderStatus.PARTIAL_FILLED, OrderStatus.PARTIAL_FILLED)

    def test_partial_filled_to_filled(self):
        assert order_fsm.can_transition(OrderStatus.PARTIAL_FILLED, OrderStatus.FILLED)

    def test_partial_filled_to_canceled(self):
        assert order_fsm.can_transition(OrderStatus.PARTIAL_FILLED, OrderStatus.CANCELED)

    # ERROR (recovery) transitions
    def test_error_to_accepted(self):
        assert order_fsm.can_transition(OrderStatus.ERROR, OrderStatus.ACCEPTED)

    def test_error_to_canceled(self):
        assert order_fsm.can_transition(OrderStatus.ERROR, OrderStatus.CANCELED)

    def test_error_to_rejected(self):
        assert order_fsm.can_transition(OrderStatus.ERROR, OrderStatus.REJECTED)

    def test_error_to_expired(self):
        assert order_fsm.can_transition(OrderStatus.ERROR, OrderStatus.EXPIRED)

    # SUSPENDED transitions
    def test_suspended_to_accepted(self):
        assert order_fsm.can_transition(OrderStatus.SUSPENDED, OrderStatus.ACCEPTED)

    def test_suspended_to_canceled(self):
        assert order_fsm.can_transition(OrderStatus.SUSPENDED, OrderStatus.CANCELED)

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
        assert OrderStatus.PENDING_SUBMIT in valid
        assert OrderStatus.CANCELED in valid
        assert len(valid) == 2

    def test_valid_transitions_from_terminal(self):
        valid = order_fsm.valid_transitions(OrderStatus.FILLED)
        assert len(valid) == 0

    def test_all_states_defined(self):
        all_states = order_fsm.get_all_states()
        assert len(all_states) == 11

    # Happy paths
    def test_full_happy_path(self):
        """Test the happy path: created → pending_submit → submitted → accepted → filled."""
        state = OrderStatus.CREATED
        state = order_fsm.transition(state, OrderStatus.PENDING_SUBMIT)
        assert state == OrderStatus.PENDING_SUBMIT
        state = order_fsm.transition(state, OrderStatus.SUBMITTED)
        assert state == OrderStatus.SUBMITTED
        state = order_fsm.transition(state, OrderStatus.ACCEPTED)
        assert state == OrderStatus.ACCEPTED
        state = order_fsm.transition(state, OrderStatus.FILLED)
        assert state == OrderStatus.FILLED
        assert order_fsm.is_terminal(state)

    def test_error_recovery_path(self):
        """Test error → accepted → partial_filled → filled."""
        state = OrderStatus.ERROR
        state = order_fsm.transition(state, OrderStatus.ACCEPTED)
        state = order_fsm.transition(state, OrderStatus.PARTIAL_FILLED)
        state = order_fsm.transition(state, OrderStatus.FILLED)
        assert order_fsm.is_terminal(state)

    def test_suspended_recovery_path(self):
        """Test suspended → accepted → filled."""
        state = OrderStatus.SUSPENDED
        state = order_fsm.transition(state, OrderStatus.ACCEPTED)
        state = order_fsm.transition(state, OrderStatus.FILLED)
        assert order_fsm.is_terminal(state)

    def test_cancel_from_created(self):
        """Test created → canceled."""
        state = OrderStatus.CREATED
        state = order_fsm.transition(state, OrderStatus.CANCELED)
        assert order_fsm.is_terminal(state)
