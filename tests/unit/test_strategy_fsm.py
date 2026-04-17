"""Tests for Strategy instance state machine (SAD 15.3)."""

import pytest

from hqmts.core.enums import StrategyStatus
from hqmts.core.exceptions import IllegalTransitionError, TerminalStateError
from hqmts.statemachine.strategy_fsm import strategy_fsm


class TestStrategyFSM:
    """Tests based on SAD 15.3 Strategy state machine."""

    # DRAFT transitions
    def test_draft_to_backtest_ready(self):
        assert strategy_fsm.can_transition(StrategyStatus.DRAFT, StrategyStatus.BACKTEST_READY)

    def test_draft_to_archived(self):
        assert strategy_fsm.can_transition(StrategyStatus.DRAFT, StrategyStatus.ARCHIVED)

    # BACKTEST_READY transitions
    def test_backtest_ready_to_validation_ready(self):
        assert strategy_fsm.can_transition(StrategyStatus.BACKTEST_READY, StrategyStatus.VALIDATION_READY)

    def test_backtest_ready_to_draft(self):
        assert strategy_fsm.can_transition(StrategyStatus.BACKTEST_READY, StrategyStatus.DRAFT)

    def test_backtest_ready_to_archived(self):
        assert strategy_fsm.can_transition(StrategyStatus.BACKTEST_READY, StrategyStatus.ARCHIVED)

    # VALIDATION_READY transitions
    def test_validation_ready_to_paper_running(self):
        assert strategy_fsm.can_transition(StrategyStatus.VALIDATION_READY, StrategyStatus.PAPER_RUNNING)

    def test_validation_ready_to_backtest_ready(self):
        assert strategy_fsm.can_transition(StrategyStatus.VALIDATION_READY, StrategyStatus.BACKTEST_READY)

    # PAPER_RUNNING transitions
    def test_paper_running_to_live_running(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAPER_RUNNING, StrategyStatus.LIVE_RUNNING)

    def test_paper_running_to_validation_ready(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAPER_RUNNING, StrategyStatus.VALIDATION_READY)

    def test_paper_running_to_paused(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAPER_RUNNING, StrategyStatus.PAUSED)

    def test_paper_running_to_archived(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAPER_RUNNING, StrategyStatus.ARCHIVED)

    # LIVE_RUNNING transitions
    def test_live_running_to_pause_open(self):
        assert strategy_fsm.can_transition(StrategyStatus.LIVE_RUNNING, StrategyStatus.PAUSE_OPEN)

    def test_live_running_to_close_only(self):
        assert strategy_fsm.can_transition(StrategyStatus.LIVE_RUNNING, StrategyStatus.CLOSE_ONLY)

    def test_live_running_to_stopped(self):
        assert strategy_fsm.can_transition(StrategyStatus.LIVE_RUNNING, StrategyStatus.STOPPED)

    def test_live_running_to_archived(self):
        assert strategy_fsm.can_transition(StrategyStatus.LIVE_RUNNING, StrategyStatus.ARCHIVED)

    # PAUSE_OPEN transitions
    def test_pause_open_to_live_running(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAUSE_OPEN, StrategyStatus.LIVE_RUNNING)

    def test_pause_open_to_close_only(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAUSE_OPEN, StrategyStatus.CLOSE_ONLY)

    def test_pause_open_to_stopped(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAUSE_OPEN, StrategyStatus.STOPPED)

    # CLOSE_ONLY transitions
    def test_close_only_to_pause_open(self):
        assert strategy_fsm.can_transition(StrategyStatus.CLOSE_ONLY, StrategyStatus.PAUSE_OPEN)

    def test_close_only_to_stopped(self):
        assert strategy_fsm.can_transition(StrategyStatus.CLOSE_ONLY, StrategyStatus.STOPPED)

    # STOPPED transitions
    def test_stopped_to_draft(self):
        assert strategy_fsm.can_transition(StrategyStatus.STOPPED, StrategyStatus.DRAFT)

    def test_stopped_to_archived(self):
        assert strategy_fsm.can_transition(StrategyStatus.STOPPED, StrategyStatus.ARCHIVED)

    # PAUSED transitions
    def test_paused_to_paper_running(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAUSED, StrategyStatus.PAPER_RUNNING)

    def test_paused_to_stopped(self):
        assert strategy_fsm.can_transition(StrategyStatus.PAUSED, StrategyStatus.STOPPED)

    # Terminal state
    def test_archived_is_terminal(self):
        assert strategy_fsm.is_terminal(StrategyStatus.ARCHIVED)

    def test_archived_has_no_transitions(self):
        assert len(strategy_fsm.valid_transitions(StrategyStatus.ARCHIVED)) == 0

    def test_terminal_transition_raises(self):
        with pytest.raises(TerminalStateError):
            strategy_fsm.transition(StrategyStatus.ARCHIVED, StrategyStatus.DRAFT)

    # Illegal transitions
    def test_draft_cannot_go_live_running(self):
        assert not strategy_fsm.can_transition(StrategyStatus.DRAFT, StrategyStatus.LIVE_RUNNING)

    def test_illegal_transition_raises(self):
        with pytest.raises(IllegalTransitionError):
            strategy_fsm.transition(StrategyStatus.DRAFT, StrategyStatus.LIVE_RUNNING)

    def test_live_running_cannot_go_to_draft(self):
        assert not strategy_fsm.can_transition(StrategyStatus.LIVE_RUNNING, StrategyStatus.DRAFT)

    # State count
    def test_all_10_states(self):
        assert len(strategy_fsm.get_all_states()) == 10

    # Lifecycle paths
    def test_full_lifecycle(self):
        """draft → backtest_ready → validation_ready → paper_running → live_running"""
        state = StrategyStatus.DRAFT
        state = strategy_fsm.transition(state, StrategyStatus.BACKTEST_READY)
        state = strategy_fsm.transition(state, StrategyStatus.VALIDATION_READY)
        state = strategy_fsm.transition(state, StrategyStatus.PAPER_RUNNING)
        state = strategy_fsm.transition(state, StrategyStatus.LIVE_RUNNING)
        assert state == StrategyStatus.LIVE_RUNNING

    def test_degradation_path(self):
        """live_running → pause_open → close_only → stopped"""
        state = StrategyStatus.LIVE_RUNNING
        state = strategy_fsm.transition(state, StrategyStatus.PAUSE_OPEN)
        state = strategy_fsm.transition(state, StrategyStatus.CLOSE_ONLY)
        state = strategy_fsm.transition(state, StrategyStatus.STOPPED)
        assert state == StrategyStatus.STOPPED

    def test_pause_and_resume(self):
        """paper_running → paused → paper_running"""
        state = StrategyStatus.PAPER_RUNNING
        state = strategy_fsm.transition(state, StrategyStatus.PAUSED)
        state = strategy_fsm.transition(state, StrategyStatus.PAPER_RUNNING)
        assert state == StrategyStatus.PAPER_RUNNING

    def test_archive_from_stopped(self):
        """stopped → archived (terminal)"""
        state = StrategyStatus.STOPPED
        state = strategy_fsm.transition(state, StrategyStatus.ARCHIVED)
        assert strategy_fsm.is_terminal(state)

    def test_restart_from_stopped(self):
        """stopped → draft (restart cycle)"""
        state = StrategyStatus.STOPPED
        state = strategy_fsm.transition(state, StrategyStatus.DRAFT)
        assert state == StrategyStatus.DRAFT
