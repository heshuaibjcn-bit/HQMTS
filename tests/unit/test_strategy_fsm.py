"""Tests for Strategy instance state machine."""

import pytest

from hqmts.core.enums import StrategyStatus
from hqmts.core.exceptions import IllegalTransitionError
from hqmts.statemachine.strategy_fsm import strategy_fsm


class TestStrategyFSM:
    """Tests based on SAD 15.3 Strategy state machine."""

    def test_draft_to_approved(self):
        assert strategy_fsm.can_transition(StrategyStatus.DRAFT, StrategyStatus.APPROVED)

    def test_draft_to_stopped(self):
        assert strategy_fsm.can_transition(StrategyStatus.DRAFT, StrategyStatus.STOPPED)

    def test_approved_to_paper_running(self):
        assert strategy_fsm.can_transition(StrategyStatus.APPROVED, StrategyStatus.PAPER_RUNNING)

    def test_approved_to_live_preparing(self):
        assert strategy_fsm.can_transition(StrategyStatus.APPROVED, StrategyStatus.LIVE_PREPARING)

    def test_paper_running_to_approved(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAPER_RUNNING, StrategyStatus.APPROVED)

    def test_live_preparing_to_pause_open(self):
        assert strategy_fsm.can_transition(StrategyStatus.LIVE_PREPARING, StrategyStatus.PAUSE_OPEN)

    def test_pause_open_to_live_running(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAUSE_OPEN, StrategyStatus.LIVE_RUNNING)

    def test_live_running_to_pause_open(self):
        assert strategy_fsm.can_transition(StrategyStatus.LIVE_RUNNING, StrategyStatus.PAUSE_OPEN)

    def test_live_running_to_close_only(self):
        assert strategy_fsm.can_transition(StrategyStatus.LIVE_RUNNING, StrategyStatus.CLOSE_ONLY)

    def test_live_running_to_recovering(self):
        assert strategy_fsm.can_transition(StrategyStatus.LIVE_RUNNING, StrategyStatus.RECOVERING)

    def test_close_only_to_pause_open(self):
        assert strategy_fsm.can_transition(StrategyStatus.CLOSE_ONLY, StrategyStatus.PAUSE_OPEN)

    def test_failed_to_recovering(self):
        assert strategy_fsm.can_transition(StrategyStatus.FAILED, StrategyStatus.RECOVERING)

    def test_recovering_to_pause_open(self):
        assert strategy_fsm.can_transition(StrategyStatus.RECOVERING, StrategyStatus.PAUSE_OPEN)

    def test_stopped_to_approved(self):
        assert strategy_fsm.can_transition(StrategyStatus.STOPPED, StrategyStatus.APPROVED)

    # Illegal transitions
    def test_draft_cannot_go_live_running(self):
        assert not strategy_fsm.can_transition(StrategyStatus.DRAFT, StrategyStatus.LIVE_RUNNING)

    def test_illegal_transition_raises(self):
        with pytest.raises(IllegalTransitionError):
            strategy_fsm.transition(StrategyStatus.DRAFT, StrategyStatus.LIVE_RUNNING)

    def test_live_running_cannot_go_to_draft(self):
        assert not strategy_fsm.can_transition(StrategyStatus.LIVE_RUNNING, StrategyStatus.DRAFT)

    # No terminal states
    def test_no_terminal_states(self):
        assert len(strategy_fsm.terminal_states) == 0

    def test_all_10_states(self):
        assert len(strategy_fsm.get_all_states()) == 10

    def test_full_lifecycle(self):
        """draft → approved → paper_running → approved → live_preparing → pause_open → live_running"""
        state = StrategyStatus.DRAFT
        state = strategy_fsm.transition(state, StrategyStatus.APPROVED)
        state = strategy_fsm.transition(state, StrategyStatus.PAPER_RUNNING)
        state = strategy_fsm.transition(state, StrategyStatus.APPROVED)
        state = strategy_fsm.transition(state, StrategyStatus.LIVE_PREPARING)
        state = strategy_fsm.transition(state, StrategyStatus.PAUSE_OPEN)
        state = strategy_fsm.transition(state, StrategyStatus.LIVE_RUNNING)
        assert state == StrategyStatus.LIVE_RUNNING

    def test_degradation_path(self):
        """live_running → pause_open → close_only → stopped"""
        state = StrategyStatus.LIVE_RUNNING
        state = strategy_fsm.transition(state, StrategyStatus.PAUSE_OPEN)
        state = strategy_fsm.transition(state, StrategyStatus.CLOSE_ONLY)
        state = strategy_fsm.transition(state, StrategyStatus.STOPPED)
        assert state == StrategyStatus.STOPPED

    def test_recovery_path(self):
        """live_running → failed → recovering → pause_open"""
        state = StrategyStatus.LIVE_RUNNING
        state = strategy_fsm.transition(state, StrategyStatus.FAILED)
        state = strategy_fsm.transition(state, StrategyStatus.RECOVERING)
        state = strategy_fsm.transition(state, StrategyStatus.PAUSE_OPEN)
        assert state == StrategyStatus.PAUSE_OPEN

    def test_live_preparing_to_live_running(self):
        """Direct transition with approval (SAD 15.3)."""
        state = strategy_fsm.transition(
            StrategyStatus.LIVE_PREPARING, StrategyStatus.LIVE_RUNNING
        )
        assert state == StrategyStatus.LIVE_RUNNING
