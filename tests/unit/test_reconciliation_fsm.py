"""Tests for Reconciliation and Recovery state machines (SAD 15.4, 15.5)."""

import pytest

from hqmts.core.enums import ReconciliationStatus, RecoveryStatus
from hqmts.core.exceptions import IllegalTransitionError, TerminalStateError
from hqmts.statemachine.reconciliation_fsm import reconciliation_fsm
from hqmts.statemachine.recovery_fsm import recovery_fsm


class TestReconciliationFSM:
    """Tests based on SAD 15.4."""

    def test_initialized_to_comparing(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.INITIALIZED, ReconciliationStatus.COMPARING
        )

    def test_initialized_to_canceled(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.INITIALIZED, ReconciliationStatus.CANCELED
        )

    def test_comparing_to_matched(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.COMPARING, ReconciliationStatus.MATCHED
        )

    def test_comparing_to_mismatched(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.COMPARING, ReconciliationStatus.MISMATCHED
        )

    def test_comparing_to_failed(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.COMPARING, ReconciliationStatus.FAILED
        )

    def test_mismatched_to_adjusting(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.MISMATCHED, ReconciliationStatus.ADJUSTING
        )

    def test_mismatched_to_escalated(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.MISMATCHED, ReconciliationStatus.ESCALATED
        )

    def test_adjusting_to_completed(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.ADJUSTING, ReconciliationStatus.COMPLETED
        )

    def test_adjusting_to_failed(self):
        assert reconciliation_fsm.can_transition(
            ReconciliationStatus.ADJUSTING, ReconciliationStatus.FAILED
        )

    # Terminal states
    def test_completed_is_terminal(self):
        assert reconciliation_fsm.is_terminal(ReconciliationStatus.COMPLETED)

    def test_failed_is_terminal(self):
        assert reconciliation_fsm.is_terminal(ReconciliationStatus.FAILED)

    def test_canceled_is_terminal(self):
        assert reconciliation_fsm.is_terminal(ReconciliationStatus.CANCELED)

    def test_escalated_is_terminal(self):
        assert reconciliation_fsm.is_terminal(ReconciliationStatus.ESCALATED)

    def test_terminal_cannot_transition(self):
        with pytest.raises(TerminalStateError):
            reconciliation_fsm.transition(ReconciliationStatus.COMPLETED, ReconciliationStatus.COMPARING)

    def test_escalated_cannot_transition(self):
        with pytest.raises(TerminalStateError):
            reconciliation_fsm.transition(ReconciliationStatus.ESCALATED, ReconciliationStatus.ADJUSTING)

    # Happy paths
    def test_happy_path(self):
        """initialized → comparing → matched → completed"""
        state = ReconciliationStatus.INITIALIZED
        state = reconciliation_fsm.transition(state, ReconciliationStatus.COMPARING)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.MATCHED)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.COMPLETED)
        assert reconciliation_fsm.is_terminal(state)

    def test_mismatch_path(self):
        """initialized → comparing → mismatched → adjusting → completed"""
        state = ReconciliationStatus.INITIALIZED
        state = reconciliation_fsm.transition(state, ReconciliationStatus.COMPARING)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.MISMATCHED)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.ADJUSTING)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.COMPLETED)
        assert reconciliation_fsm.is_terminal(state)

    def test_cancel_path(self):
        """initialized → canceled"""
        state = ReconciliationStatus.INITIALIZED
        state = reconciliation_fsm.transition(state, ReconciliationStatus.CANCELED)
        assert reconciliation_fsm.is_terminal(state)

    def test_escalate_path(self):
        """initialized → comparing → mismatched → escalated"""
        state = ReconciliationStatus.INITIALIZED
        state = reconciliation_fsm.transition(state, ReconciliationStatus.COMPARING)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.MISMATCHED)
        state = reconciliation_fsm.transition(state, ReconciliationStatus.ESCALATED)
        assert reconciliation_fsm.is_terminal(state)

    def test_all_9_states(self):
        assert len(reconciliation_fsm.get_all_states()) == 9


class TestRecoveryFSM:
    """Tests based on SAD 15.5."""

    def test_created_to_diagnosing(self):
        assert recovery_fsm.can_transition(RecoveryStatus.CREATED, RecoveryStatus.DIAGNOSING)

    def test_created_to_canceled(self):
        assert recovery_fsm.can_transition(RecoveryStatus.CREATED, RecoveryStatus.CANCELED)

    def test_diagnosing_to_recovering(self):
        assert recovery_fsm.can_transition(RecoveryStatus.DIAGNOSING, RecoveryStatus.RECOVERING)

    def test_diagnosing_to_failed(self):
        assert recovery_fsm.can_transition(RecoveryStatus.DIAGNOSING, RecoveryStatus.FAILED)

    def test_recovering_to_verifying(self):
        assert recovery_fsm.can_transition(RecoveryStatus.RECOVERING, RecoveryStatus.VERIFYING)

    def test_recovering_to_failed(self):
        assert recovery_fsm.can_transition(RecoveryStatus.RECOVERING, RecoveryStatus.FAILED)

    def test_verifying_to_completed(self):
        assert recovery_fsm.can_transition(RecoveryStatus.VERIFYING, RecoveryStatus.COMPLETED)

    def test_verifying_can_loop_to_recovering(self):
        assert recovery_fsm.can_transition(RecoveryStatus.VERIFYING, RecoveryStatus.RECOVERING)

    def test_verifying_to_failed(self):
        assert recovery_fsm.can_transition(RecoveryStatus.VERIFYING, RecoveryStatus.FAILED)

    # Terminal states
    def test_completed_is_terminal(self):
        assert recovery_fsm.is_terminal(RecoveryStatus.COMPLETED)

    def test_failed_is_terminal(self):
        assert recovery_fsm.is_terminal(RecoveryStatus.FAILED)

    def test_canceled_is_terminal(self):
        assert recovery_fsm.is_terminal(RecoveryStatus.CANCELED)

    def test_terminal_cannot_transition(self):
        with pytest.raises(TerminalStateError):
            recovery_fsm.transition(RecoveryStatus.COMPLETED, RecoveryStatus.DIAGNOSING)

    def test_failed_cannot_transition(self):
        with pytest.raises(TerminalStateError):
            recovery_fsm.transition(RecoveryStatus.FAILED, RecoveryStatus.DIAGNOSING)

    # Full paths
    def test_full_recovery_path(self):
        """created → diagnosing → recovering → verifying → completed"""
        state = RecoveryStatus.CREATED
        state = recovery_fsm.transition(state, RecoveryStatus.DIAGNOSING)
        state = recovery_fsm.transition(state, RecoveryStatus.RECOVERING)
        state = recovery_fsm.transition(state, RecoveryStatus.VERIFYING)
        state = recovery_fsm.transition(state, RecoveryStatus.COMPLETED)
        assert recovery_fsm.is_terminal(state)

    def test_cancel_from_created(self):
        state = RecoveryStatus.CREATED
        state = recovery_fsm.transition(state, RecoveryStatus.CANCELED)
        assert recovery_fsm.is_terminal(state)

    def test_cancel_from_diagnosing(self):
        assert recovery_fsm.can_transition(RecoveryStatus.DIAGNOSING, RecoveryStatus.CANCELED)

    def test_fail_during_diagnosing(self):
        state = RecoveryStatus.CREATED
        state = recovery_fsm.transition(state, RecoveryStatus.DIAGNOSING)
        state = recovery_fsm.transition(state, RecoveryStatus.FAILED)
        assert recovery_fsm.is_terminal(state)

    def test_verify_loop_back(self):
        """verifying → recovering → verifying → completed"""
        state = RecoveryStatus.CREATED
        state = recovery_fsm.transition(state, RecoveryStatus.DIAGNOSING)
        state = recovery_fsm.transition(state, RecoveryStatus.RECOVERING)
        state = recovery_fsm.transition(state, RecoveryStatus.VERIFYING)
        state = recovery_fsm.transition(state, RecoveryStatus.RECOVERING)
        state = recovery_fsm.transition(state, RecoveryStatus.VERIFYING)
        state = recovery_fsm.transition(state, RecoveryStatus.COMPLETED)
        assert recovery_fsm.is_terminal(state)

    def test_all_7_states(self):
        assert len(recovery_fsm.get_all_states()) == 7
