"""Tests for governance layer state machines (CashReservation, AgentTask, AgentProposal, ApprovalRequest)."""

from __future__ import annotations

import pytest

from hqmts.core.enums import (
    AgentTaskStatus,
    ApprovalStatus,
    ProposalStatus,
    ReservationStatus,
)
from hqmts.core.exceptions import IllegalTransitionError, TerminalStateError
from hqmts.statemachine.agent_proposal_fsm import agent_proposal_fsm
from hqmts.statemachine.agent_task_fsm import agent_task_fsm
from hqmts.statemachine.approval_fsm import approval_fsm
from hqmts.statemachine.reservation_fsm import reservation_fsm


# ── CashReservation FSM ────────────────────────────────────────────────────────


class TestReservationFSM:
    def test_active_to_partially_consumed(self):
        assert reservation_fsm.transition(ReservationStatus.ACTIVE, ReservationStatus.PARTIALLY_CONSUMED)

    def test_active_to_fully_consumed(self):
        assert reservation_fsm.transition(ReservationStatus.ACTIVE, ReservationStatus.FULLY_CONSUMED) == ReservationStatus.FULLY_CONSUMED

    def test_active_to_released(self):
        assert reservation_fsm.transition(ReservationStatus.ACTIVE, ReservationStatus.RELEASED) == ReservationStatus.RELEASED

    def test_active_to_expired(self):
        assert reservation_fsm.transition(ReservationStatus.ACTIVE, ReservationStatus.EXPIRED) == ReservationStatus.EXPIRED

    def test_active_to_invalid(self):
        assert reservation_fsm.transition(ReservationStatus.ACTIVE, ReservationStatus.INVALID) == ReservationStatus.INVALID

    def test_partially_consumed_to_fully_consumed(self):
        assert reservation_fsm.transition(ReservationStatus.PARTIALLY_CONSUMED, ReservationStatus.FULLY_CONSUMED) == ReservationStatus.FULLY_CONSUMED

    def test_partially_consumed_to_released(self):
        assert reservation_fsm.transition(ReservationStatus.PARTIALLY_CONSUMED, ReservationStatus.RELEASED) == ReservationStatus.RELEASED

    def test_terminal_fully_consumed(self):
        assert reservation_fsm.is_terminal(ReservationStatus.FULLY_CONSUMED)

    def test_terminal_released(self):
        assert reservation_fsm.is_terminal(ReservationStatus.RELEASED)

    def test_terminal_expired(self):
        assert reservation_fsm.is_terminal(ReservationStatus.EXPIRED)

    def test_terminal_invalid(self):
        assert reservation_fsm.is_terminal(ReservationStatus.INVALID)

    def test_terminal_raises(self):
        with pytest.raises(TerminalStateError):
            reservation_fsm.transition(ReservationStatus.FULLY_CONSUMED, ReservationStatus.ACTIVE)

    def test_illegal_transition(self):
        with pytest.raises(IllegalTransitionError):
            reservation_fsm.transition(ReservationStatus.ACTIVE, ReservationStatus.ACTIVE)

    def test_valid_transitions_from_active(self):
        vt = reservation_fsm.valid_transitions(ReservationStatus.ACTIVE)
        assert set(vt) == {
            ReservationStatus.PARTIALLY_CONSUMED,
            ReservationStatus.FULLY_CONSUMED,
            ReservationStatus.RELEASED,
            ReservationStatus.EXPIRED,
            ReservationStatus.INVALID,
        }

    def test_no_transitions_from_terminal(self):
        assert reservation_fsm.valid_transitions(ReservationStatus.RELEASED) == []

    def test_all_states_defined(self):
        states = reservation_fsm.get_all_states()
        assert set(states) == set(ReservationStatus)


# ── AgentTask FSM ──────────────────────────────────────────────────────────────


class TestAgentTaskFSM:
    def test_created_to_planning(self):
        assert agent_task_fsm.transition(AgentTaskStatus.CREATED, AgentTaskStatus.PLANNING) == AgentTaskStatus.PLANNING

    def test_created_to_canceled(self):
        assert agent_task_fsm.transition(AgentTaskStatus.CREATED, AgentTaskStatus.CANCELED) == AgentTaskStatus.CANCELED

    def test_planning_to_running(self):
        assert agent_task_fsm.transition(AgentTaskStatus.PLANNING, AgentTaskStatus.RUNNING) == AgentTaskStatus.RUNNING

    def test_planning_to_failed(self):
        assert agent_task_fsm.transition(AgentTaskStatus.PLANNING, AgentTaskStatus.FAILED) == AgentTaskStatus.FAILED

    def test_running_to_waiting_tool(self):
        assert agent_task_fsm.transition(AgentTaskStatus.RUNNING, AgentTaskStatus.WAITING_TOOL) == AgentTaskStatus.WAITING_TOOL

    def test_running_to_completed(self):
        assert agent_task_fsm.transition(AgentTaskStatus.RUNNING, AgentTaskStatus.COMPLETED) == AgentTaskStatus.COMPLETED

    def test_running_to_escalated(self):
        assert agent_task_fsm.transition(AgentTaskStatus.RUNNING, AgentTaskStatus.ESCALATED) == AgentTaskStatus.ESCALATED

    def test_waiting_tool_back_to_running(self):
        assert agent_task_fsm.transition(AgentTaskStatus.WAITING_TOOL, AgentTaskStatus.RUNNING) == AgentTaskStatus.RUNNING

    def test_timeout_to_escalated(self):
        assert agent_task_fsm.transition(AgentTaskStatus.TIMEOUT, AgentTaskStatus.ESCALATED) == AgentTaskStatus.ESCALATED

    def test_terminal_states(self):
        for s in (AgentTaskStatus.COMPLETED, AgentTaskStatus.FAILED, AgentTaskStatus.CANCELED, AgentTaskStatus.ESCALATED):
            assert agent_task_fsm.is_terminal(s), f"{s} should be terminal"

    def test_terminal_raises(self):
        with pytest.raises(TerminalStateError):
            agent_task_fsm.transition(AgentTaskStatus.COMPLETED, AgentTaskStatus.RUNNING)

    def test_illegal_created_to_running(self):
        with pytest.raises(IllegalTransitionError):
            agent_task_fsm.transition(AgentTaskStatus.CREATED, AgentTaskStatus.RUNNING)

    def test_illegal_running_to_created(self):
        with pytest.raises(IllegalTransitionError):
            agent_task_fsm.transition(AgentTaskStatus.RUNNING, AgentTaskStatus.CREATED)

    def test_illegal_timeout_to_running(self):
        """Timeout can only escalate, not go back to running."""
        with pytest.raises(IllegalTransitionError):
            agent_task_fsm.transition(AgentTaskStatus.TIMEOUT, AgentTaskStatus.RUNNING)

    def test_valid_transitions_from_running(self):
        vt = agent_task_fsm.valid_transitions(AgentTaskStatus.RUNNING)
        assert set(vt) == {
            AgentTaskStatus.WAITING_TOOL,
            AgentTaskStatus.COMPLETED,
            AgentTaskStatus.FAILED,
            AgentTaskStatus.TIMEOUT,
            AgentTaskStatus.ESCALATED,
        }

    def test_all_states_defined(self):
        states = agent_task_fsm.get_all_states()
        assert set(states) == set(AgentTaskStatus)

    def test_full_lifecycle(self):
        """created → planning → running → waiting_tool → running → completed"""
        state = agent_task_fsm.transition(AgentTaskStatus.CREATED, AgentTaskStatus.PLANNING)
        state = agent_task_fsm.transition(state, AgentTaskStatus.RUNNING)
        state = agent_task_fsm.transition(state, AgentTaskStatus.WAITING_TOOL)
        state = agent_task_fsm.transition(state, AgentTaskStatus.RUNNING)
        state = agent_task_fsm.transition(state, AgentTaskStatus.COMPLETED)
        assert state == AgentTaskStatus.COMPLETED


# ── AgentProposal FSM ──────────────────────────────────────────────────────────


class TestAgentProposalFSM:
    def test_drafted_to_policy_checking(self):
        assert agent_proposal_fsm.transition(ProposalStatus.DRAFTED, ProposalStatus.POLICY_CHECKING) == ProposalStatus.POLICY_CHECKING

    def test_drafted_to_canceled(self):
        assert agent_proposal_fsm.transition(ProposalStatus.DRAFTED, ProposalStatus.CANCELED) == ProposalStatus.CANCELED

    def test_policy_checking_to_policy_rejected(self):
        assert agent_proposal_fsm.transition(ProposalStatus.POLICY_CHECKING, ProposalStatus.POLICY_REJECTED) == ProposalStatus.POLICY_REJECTED

    def test_policy_checking_to_pending_approval(self):
        assert agent_proposal_fsm.transition(ProposalStatus.POLICY_CHECKING, ProposalStatus.PENDING_APPROVAL) == ProposalStatus.PENDING_APPROVAL

    def test_pending_approval_to_approved(self):
        assert agent_proposal_fsm.transition(ProposalStatus.PENDING_APPROVAL, ProposalStatus.APPROVED) == ProposalStatus.APPROVED

    def test_pending_approval_to_rejected(self):
        assert agent_proposal_fsm.transition(ProposalStatus.PENDING_APPROVAL, ProposalStatus.REJECTED) == ProposalStatus.REJECTED

    def test_approved_to_execution_pending(self):
        assert agent_proposal_fsm.transition(ProposalStatus.APPROVED, ProposalStatus.EXECUTION_PENDING) == ProposalStatus.EXECUTION_PENDING

    def test_execution_pending_to_executed(self):
        assert agent_proposal_fsm.transition(ProposalStatus.EXECUTION_PENDING, ProposalStatus.EXECUTED) == ProposalStatus.EXECUTED

    def test_execution_pending_to_execution_failed(self):
        assert agent_proposal_fsm.transition(ProposalStatus.EXECUTION_PENDING, ProposalStatus.EXECUTION_FAILED) == ProposalStatus.EXECUTION_FAILED

    def test_terminal_states(self):
        for s in (ProposalStatus.POLICY_REJECTED, ProposalStatus.REJECTED, ProposalStatus.EXECUTED, ProposalStatus.EXECUTION_FAILED, ProposalStatus.EXPIRED, ProposalStatus.CANCELED):
            assert agent_proposal_fsm.is_terminal(s), f"{s} should be terminal"

    def test_terminal_raises(self):
        with pytest.raises(TerminalStateError):
            agent_proposal_fsm.transition(ProposalStatus.EXECUTED, ProposalStatus.DRAFTED)

    def test_illegal_drafted_to_approved(self):
        """Cannot skip policy checking."""
        with pytest.raises(IllegalTransitionError):
            agent_proposal_fsm.transition(ProposalStatus.DRAFTED, ProposalStatus.APPROVED)

    def test_illegal_approved_to_rejected(self):
        """Approved can only go to execution_pending."""
        with pytest.raises(IllegalTransitionError):
            agent_proposal_fsm.transition(ProposalStatus.APPROVED, ProposalStatus.REJECTED)

    def test_all_states_defined(self):
        states = agent_proposal_fsm.get_all_states()
        assert set(states) == set(ProposalStatus)

    def test_full_happy_path(self):
        """drafted → policy_checking → pending_approval → approved → execution_pending → executed"""
        state = agent_proposal_fsm.transition(ProposalStatus.DRAFTED, ProposalStatus.POLICY_CHECKING)
        state = agent_proposal_fsm.transition(state, ProposalStatus.PENDING_APPROVAL)
        state = agent_proposal_fsm.transition(state, ProposalStatus.APPROVED)
        state = agent_proposal_fsm.transition(state, ProposalStatus.EXECUTION_PENDING)
        state = agent_proposal_fsm.transition(state, ProposalStatus.EXECUTED)
        assert state == ProposalStatus.EXECUTED

    def test_policy_rejection_path(self):
        """drafted → policy_checking → policy_rejected"""
        state = agent_proposal_fsm.transition(ProposalStatus.DRAFTED, ProposalStatus.POLICY_CHECKING)
        state = agent_proposal_fsm.transition(state, ProposalStatus.POLICY_REJECTED)
        assert state == ProposalStatus.POLICY_REJECTED


# ── ApprovalRequest FSM ────────────────────────────────────────────────────────


class TestApprovalFSM:
    def test_pending_to_approved(self):
        assert approval_fsm.transition(ApprovalStatus.PENDING, ApprovalStatus.APPROVED) == ApprovalStatus.APPROVED

    def test_pending_to_rejected(self):
        assert approval_fsm.transition(ApprovalStatus.PENDING, ApprovalStatus.REJECTED) == ApprovalStatus.REJECTED

    def test_pending_to_expired(self):
        assert approval_fsm.transition(ApprovalStatus.PENDING, ApprovalStatus.EXPIRED) == ApprovalStatus.EXPIRED

    def test_pending_to_canceled(self):
        assert approval_fsm.transition(ApprovalStatus.PENDING, ApprovalStatus.CANCELED) == ApprovalStatus.CANCELED

    def test_terminal_states(self):
        for s in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED, ApprovalStatus.CANCELED):
            assert approval_fsm.is_terminal(s), f"{s} should be terminal"

    def test_terminal_raises(self):
        with pytest.raises(TerminalStateError):
            approval_fsm.transition(ApprovalStatus.APPROVED, ApprovalStatus.REJECTED)

    def test_illegal_pending_to_pending(self):
        with pytest.raises(IllegalTransitionError):
            approval_fsm.transition(ApprovalStatus.PENDING, ApprovalStatus.PENDING)

    def test_all_states_defined(self):
        states = approval_fsm.get_all_states()
        assert set(states) == set(ApprovalStatus)

    def test_valid_transitions_from_pending(self):
        vt = approval_fsm.valid_transitions(ApprovalStatus.PENDING)
        assert set(vt) == {
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.CANCELED,
        }

    def test_no_transitions_from_terminal(self):
        for s in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED, ApprovalStatus.CANCELED):
            assert approval_fsm.valid_transitions(s) == []
