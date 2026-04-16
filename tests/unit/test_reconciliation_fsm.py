"""Tests for Reconciliation and Recovery state machines."""

import pytest

from hqmts.core.enums import ReconciliationStatus, RecoveryStatus
from hqmts.core.exceptions import IllegalTransitionError, TerminalStateError
from hqmts.statemachine.reconciliation_fsm import reconciliation_fsm
from hqmts.statemachine.recovery_fsm import recovery_fsm


class TestReconciliationFSM:
    """Tests based on SAD 15.4."""

    def test_pending_to_running(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.PENDING, ReconciliationStatus.RUNNING
        )

    def test_running_to_matched(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.RUNNING, ReconciliationStatus.MATCHED
        )

    def test_running_to_mismatch(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.RUNNING, ReconciliationStatus.MISMATCH_DETECTED
        )

    def test_mismatch_to_corrected(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.MISMATCH_DETECTED, ReconciliationStatus.CORRECTED
        )

    def test_mismatch_to_escalated(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.MISMATCH_DETECTED, ReconciliationStatus.ESCALATED
        )

    def test_closed_is_terminal(self):
        assert reconciliation_fsm.is_terminal(ReconciliationStatus.CLOSED)

    def test_closed_cannot_transition(self):
        with pytest.raises(TerminalStateError):
            reconciliation_fsm.transition(ReconciliationStatus.CLOSED, ReconciliationStatus.RUNNING)

    def test_matched_to_closed(self):
        state = reconciliation_fsm.transition(
            ReconciliationStatus.MATCHED, ReconciliationStatus.CLOSED
        )
        assert state == ReconciliationStatus.CLOSED

    def test_happy_path(self):
        state = ReconciliationStatus.PENDING
        state = reconciliation_fsm.transition(state, ReconciliationStatus.RUNNING)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.MATCHED)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.CLOSED)
        assert reconciliation_fsm.is_terminal(state)

    def test_mismatch_path(self):
        state = ReconciliationStatus.PENDING
        state = reconciliation_fsm.transition(state, ReconciliationStatus.RUNNING)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.MISMATCH_DETECTED)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.CORRECTED)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.CLOSED)
        assert reconciliation_fsm.is_terminal(state)


class TestRecoveryFSM:
    """Tests based on SAD 15.5."""

    def test_created_to_loading_state(self):
        assert recovery_fsm.can_transition(RecoveryStatus.CREATED, RecoveryStatus.LOADING_STATE)

    def test_loading_to_reconciling(self):
        assert recovery_fsm.can_transition(RecoveryStatus.LOADING_STATE, RecoveryStatus.RECONCILING)

    def test_reconciling_to_rebuilding(self):
        assert recovery_fsm.can_transition(RecoveryStatus.RECONCILING, RecoveryStatus.REBUILDING_CONTEXT)

    def test_rebuilding_to_pending_confirmation(self):
        assert recovery_fsm.can_transition(
            RecoveryStatus.REBUILDING_CONTEXT, RecoveryStatus.PENDING_CONFIRMATION
        )

    def test_pending_to_completed(self):
        assert recovery_fsm.can_transition(
            RecoveryStatus.PENDING_CONFIRMATION, RecoveryStatus.COMPLETED
        )

    def test_completed_is_terminal(self):
        assert recovery_fsm.is_terminal(RecoveryStatus.COMPLETED)

    def test_aborted_is_terminal(self):
        assert recovery_fsm.is_terminal(RecoveryStatus.ABORTED)

    def test_escalated_can_return_to_pending(self):
        assert recovery_fsm.can_transition(
            RecoveryStatus.ESCALATED, RecoveryStatus.PENDING_CONFIRMATION
        )

    def test_full_recovery_path(self):
        state = RecoveryStatus.CREATED
        state = recovery_fsm.transition(state, RecoveryStatus.LOADING_STATE)
        state = recovery_fsm.transition(state, RecoveryStatus.RECONCILING)
        state = recovery_fsm.transition(state, RecoveryStatus.REBUILDING_CONTEXT)
        state = recovery_fsm.transition(state, RecoveryStatus.PENDING_CONFIRMATION)
        state = recovery_fsm.transition(state, RecoveryStatus.COMPLETED)
        assert recovery_fsm.is_terminal(state)

    def test_abort_from_any_non_terminal(self):
        """Abort can happen from most non-terminal states."""
        assert recovery_fsm.can_transition(RecoveryStatus.CREATED, RecoveryStatus.ABORTED)
        assert recovery_fsm.can_transition(RecoveryStatus.LOADING_STATE, RecoveryStatus.ABORTED)
        assert recovery_fsm.can_transition(RecoveryStatus.RECONCILING, RecoveryStatus.ABORTED)
