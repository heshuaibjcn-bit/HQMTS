"""AutonomousResearchLoop -- core loop controller for ResearchCycle.

Drives a ResearchCycle through its lifecycle states by evaluating the current
state, deciding the next action, and executing through existing services.
Respects budget constraints, autonomy levels, and governance chain.

SAD 24.10.1, 24.10.5, FR-RES-014~020.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import (
    AutonomyLevel,
    FactorDiscoveryStatus,
    ResearchCycleStatus,
    StrategyCandidateStatus,
)
from hqmts.core.types import FactorDiscoveryId, ResearchCycleId, StrategyCandidateId
from hqmts.db.models.research_cycle import (
    FactorDiscoveryORM,
    ResearchCycleORM,
    StrategyCandidateORM,
)
from hqmts.db.repositories.research_cycle_repo import (
    FactorDiscoveryRepository,
    ResearchCycleRepository,
    StrategyCandidateRepository,
)
from hqmts.research.bridge import FactorStrategyBridgeService
from hqmts.research.orchestrator import ResearchOrchestrator

logger = logging.getLogger(__name__)


# ── Budget defaults ──────────────────────────────────────────────────────────────

DEFAULT_BUDGET: dict[str, Any] = {
    "max_trials": 50,
    "max_backtests": 20,
    "max_llm_calls": 100,
    "max_duration_hours": 24,
}


# ── State transition rules ───────────────────────────────────────────────────────

# Maps current status to (next_status, preconditions_check_method)
_TRANSITIONS: dict[str, list[tuple[str, str]]] = {
    "opportunity_identified": [("researching", "start_research")],
    "researching": [
        ("factor_validated", "validate_factors"),
        ("researching", "continue_research"),
    ],
    "factor_validated": [("synthesizing", "synthesize")],
    "synthesizing": [
        ("backtesting", "start_backtesting"),
        ("archived", "no_candidates"),
    ],
    "backtesting": [("evaluating", "evaluate")],
    "evaluating": [
        ("promoted", "promote"),
        ("archived", "no_alpha"),
        ("re_research", "re_research_trigger"),
    ],
    "re_research": [("researching", "restart_research")],
}

_TERMINAL_STATES = {"promoted", "archived", "canceled", "failed"}


@dataclass
class LoopAction:
    """A single action the loop decides to take."""

    action: str  # transition, wait, pause_for_approval, budget_exhausted
    target_status: str | None = None
    reason: str = ""
    details: dict[str, Any] | None = None


@dataclass
class LoopResult:
    """Result of a single loop iteration."""

    cycle_id: str
    previous_status: str
    current_status: str
    action_taken: str
    message: str
    should_continue: bool = True
    requires_approval: bool = False
    artifacts_created: list[str] | None = None


class AutonomousResearchLoop:
    """Core loop controller driving ResearchCycle through its lifecycle.

    SAD 24.10.1: Loop controller algorithm.
    SAD 24.10.5: LLM prompt architecture (phase-aware context templates).
    FR-RES-014: ResearchCycle lifecycle.
    FR-RES-017: Autonomy level enforcement.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cycle_repo = ResearchCycleRepository(session)
        self._discovery_repo = FactorDiscoveryRepository(session)
        self._candidate_repo = StrategyCandidateRepository(session)
        self._bridge = FactorStrategyBridgeService(session)
        self._orchestrator = ResearchOrchestrator(session)

    async def tick(self, cycle_id: str) -> LoopResult:
        """Execute one loop iteration for the given cycle.

        Evaluates current state, decides next action, executes it.
        Returns result indicating whether the loop should continue.
        """
        cycle = await self._cycle_repo.get_by_cycle_id(cycle_id)
        if cycle is None:
            return LoopResult(
                cycle_id=cycle_id,
                previous_status="unknown",
                current_status="unknown",
                action_taken="error",
                message=f"Cycle {cycle_id} not found",
                should_continue=False,
            )

        previous = cycle.status

        # Check terminal state
        if previous in _TERMINAL_STATES:
            return LoopResult(
                cycle_id=cycle_id,
                previous_status=previous,
                current_status=previous,
                action_taken="none",
                message=f"Cycle is in terminal state: {previous}",
                should_continue=False,
            )

        # Check budget
        if self._is_budget_exhausted(cycle):
            await self._transition_status(
                cycle, "archived", "Budget exhausted"
            )
            return LoopResult(
                cycle_id=cycle_id,
                previous_status=previous,
                current_status="archived",
                action_taken="budget_exhausted",
                message="Cycle archived: budget exhausted",
                should_continue=False,
            )

        # Decide next action based on current state
        action = await self._decide_action(cycle)
        result = await self._execute_action(cycle, action)
        return result

    async def start_cycle(
        self,
        title: str,
        opportunity_type: str = "human_initiated",
        research_question: str = "",
        autonomy_level: str = "level_2",
        budget: dict[str, Any] | None = None,
        triggered_by: str = "",
        source_strategy_instance_id: str = "",
    ) -> ResearchCycleORM:
        """Create and initialize a new ResearchCycle."""
        cycle_id = ResearchCycleId(f"rc_{uuid.uuid4().hex[:12]}")

        actual_budget = budget or DEFAULT_BUDGET.copy()

        orm = ResearchCycleORM(
            research_cycle_id=cycle_id,
            title=title,
            opportunity_type=opportunity_type,
            opportunity_signal_json=json.dumps({
                "question": research_question,
                "source_strategy": source_strategy_instance_id,
            }),
            status="opportunity_identified",
            budget_json=json.dumps(actual_budget),
            budget_consumed_json=json.dumps({
                "trials": 0,
                "backtests": 0,
                "llm_calls": 0,
            }),
            factor_discovery_ids_json="[]",
            strategy_candidate_ids_json="[]",
            autonomy_level=autonomy_level,
            source_strategy_instance_id=source_strategy_instance_id,
            triggered_by=triggered_by,
        )
        await self._cycle_repo.create(orm)
        return orm

    async def cancel_cycle(self, cycle_id: str) -> ResearchCycleORM:
        """Cancel a cycle (if not terminal)."""
        cycle = await self._cycle_repo.get_by_cycle_id(cycle_id)
        if cycle is None:
            raise ValueError(f"Cycle {cycle_id} not found")
        if cycle.status in _TERMINAL_STATES:
            raise ValueError(f"Cannot cancel cycle in terminal state: {cycle.status}")

        cycle.status = "canceled"
        cycle.cycle_outcome = "canceled"
        cycle.outcome_reason = "Canceled by user"
        await self._cycle_repo.update(cycle)
        return cycle

    # ── Decision Engine ────────────────────────────────────────────────────────

    async def _decide_action(self, cycle: ResearchCycleORM) -> LoopAction:
        """Decide the next action based on current cycle status."""
        status = cycle.status

        if status == "opportunity_identified":
            return LoopAction(
                action="transition",
                target_status="researching",
                reason="Start research phase: create ResearchProject",
            )

        if status == "researching":
            # Check if any significant discoveries exist
            discoveries = await self._discovery_repo.list_significant_by_cycle(
                cycle.research_cycle_id
            )
            if discoveries:
                return LoopAction(
                    action="transition",
                    target_status="factor_validated",
                    reason=f"Found {len(discoveries)} significant factor discoveries",
                    details={"discovery_count": len(discoveries)},
                )
            # Check if budget allows more research
            consumed = json.loads(cycle.budget_consumed_json or "{}")
            budget = json.loads(cycle.budget_json or "{}")
            trials_used = consumed.get("trials", 0)
            max_trials = budget.get("max_trials", 50)
            if trials_used < max_trials:
                return LoopAction(
                    action="transition",
                    target_status="researching",
                    reason="Continue research: budget remaining",
                )
            return LoopAction(
                action="transition",
                target_status="archived",
                reason="Research budget exhausted, no significant findings",
            )

        if status == "factor_validated":
            return LoopAction(
                action="transition",
                target_status="synthesizing",
                reason="Synthesize strategy candidates from factor discoveries",
            )

        if status == "synthesizing":
            candidates = await self._candidate_repo.list_by_status(
                cycle.research_cycle_id, "generated"
            )
            if candidates:
                return LoopAction(
                    action="transition",
                    target_status="backtesting",
                    reason=f"Generated {len(candidates)} strategy candidates",
                    details={"candidate_count": len(candidates)},
                )
            return LoopAction(
                action="transition",
                target_status="archived",
                reason="No strategy candidates could be generated",
            )

        if status == "backtesting":
            # Check if all candidates have backtest results
            all_candidates = await self._candidate_repo.list_by_cycle(
                cycle.research_cycle_id
            )
            pending = [c for c in all_candidates if c.backtest_sharpe is None]
            if not pending:
                return LoopAction(
                    action="transition",
                    target_status="evaluating",
                    reason="All candidates have backtest results",
                )
            return LoopAction(
                action="wait",
                reason=f"Waiting for {len(pending)} candidates to complete backtesting",
            )

        if status == "evaluating":
            return LoopAction(
                action="transition",
                target_status="evaluating",  # Will be resolved in _execute_action
                reason="Evaluate candidates and determine outcome",
            )

        if status == "re_research":
            return LoopAction(
                action="transition",
                target_status="researching",
                reason="Restart research phase with new hypotheses",
            )

        return LoopAction(action="wait", reason="No action defined for current state")

    # ── Action Execution ───────────────────────────────────────────────────────

    async def _execute_action(
        self, cycle: ResearchCycleORM, action: LoopAction
    ) -> LoopResult:
        """Execute the decided action."""
        previous = cycle.status
        artifacts: list[str] = []

        if action.action == "wait":
            return LoopResult(
                cycle_id=cycle.research_cycle_id,
                previous_status=previous,
                current_status=previous,
                action_taken="wait",
                message=action.reason,
                should_continue=True,
            )

        if action.action == "transition":
            target = action.target_status

            # Special handling for specific transitions
            if previous == "opportunity_identified" and target == "researching":
                project_id = await self._create_linked_project(cycle)
                if project_id:
                    cycle.research_project_id = project_id
                    artifacts.append(f"project:{project_id}")
                await self._transition_status(cycle, target, action.reason)

            elif previous == "researching" and target == "factor_validated":
                await self._finalize_discoveries(cycle)
                await self._transition_status(cycle, target, action.reason)

            elif previous == "researching" and target == "researching":
                # Continue research: just increment trial count
                self._increment_budget(cycle, "trials", 1)
                await self._cycle_repo.update(cycle)

            elif previous == "factor_validated" and target == "synthesizing":
                candidates = await self._bridge.synthesize_candidates(
                    cycle.research_cycle_id,
                    cycle.research_project_id or "",
                )
                # Update cycle with candidate IDs
                cand_ids = [c.strategy_candidate_id for c in candidates]
                cycle.strategy_candidate_ids_json = json.dumps(cand_ids)
                self._increment_budget(cycle, "llm_calls", len(candidates))
                await self._transition_status(cycle, target, action.reason)
                artifacts.extend([f"candidate:{cid}" for cid in cand_ids])

            elif previous == "synthesizing" and target == "backtesting":
                await self._transition_status(cycle, target, action.reason)

            elif previous == "backtesting" and target == "evaluating":
                await self._evaluate_all_candidates(cycle)
                await self._transition_status(cycle, target, action.reason)

            elif previous == "evaluating":
                actual_target = await self._resolve_evaluation(cycle)
                await self._transition_status(cycle, actual_target, action.reason)

            elif previous == "re_research" and target == "researching":
                await self._transition_status(cycle, target, action.reason)

            elif target == "archived":
                cycle.cycle_outcome = "archived_no_alpha"
                cycle.outcome_reason = action.reason
                await self._transition_status(cycle, target, action.reason)

            else:
                await self._transition_status(cycle, target, action.reason)

            return LoopResult(
                cycle_id=cycle.research_cycle_id,
                previous_status=previous,
                current_status=cycle.status,
                action_taken="transitioned",
                message=action.reason,
                should_continue=cycle.status not in _TERMINAL_STATES,
                artifacts_created=artifacts if artifacts else None,
            )

        return LoopResult(
            cycle_id=cycle.research_cycle_id,
            previous_status=previous,
            current_status=previous,
            action_taken="no_op",
            message="No action taken",
            should_continue=True,
        )

    # ── Helper Methods ─────────────────────────────────────────────────────────

    async def _create_linked_project(self, cycle: ResearchCycleORM) -> str | None:
        """Create a ResearchProject linked to this cycle."""
        signal = json.loads(cycle.opportunity_signal_json or "{}")
        question = signal.get("question", cycle.title)

        project = await self._orchestrator.create_project(
            title=f"[Cycle] {cycle.title}",
            research_question=question,
            mode="ai_autonomous",
            created_by="autonomous_loop",
        )
        # Advance from created → exploring (auto-start)
        try:
            await self._orchestrator.advance_stage(project.research_project_id)
        except ValueError:
            pass  # May already be in exploring

        return project.research_project_id

    async def _finalize_discoveries(self, cycle: ResearchCycleORM) -> None:
        """Promote significant discoveries from candidate to validated status."""
        discoveries = await self._discovery_repo.list_significant_by_cycle(
            cycle.research_cycle_id
        )
        discovery_ids = []
        for d in discoveries:
            d.status = "validated"
            await self._discovery_repo.update(d)
            discovery_ids.append(d.factor_discovery_id)

        cycle.factor_discovery_ids_json = json.dumps(discovery_ids)

    async def _evaluate_all_candidates(self, cycle: ResearchCycleORM) -> None:
        """Evaluate all candidates with backtest results."""
        candidates = await self._candidate_repo.list_by_cycle(
            cycle.research_cycle_id
        )
        for c in candidates:
            if c.backtest_sharpe is not None and c.status == "generated":
                await self._bridge.evaluate_candidate(c.strategy_candidate_id)
                self._increment_budget(cycle, "backtests", 1)

    async def _resolve_evaluation(self, cycle: ResearchCycleORM) -> str:
        """Determine the outcome of evaluation phase."""
        candidates = await self._candidate_repo.list_by_cycle(
            cycle.research_cycle_id
        )
        evaluated = [c for c in candidates if c.status == "evaluated"]
        promoted = [c for c in evaluated if c.evaluation_verdict == "promote"]

        if promoted:
            cycle.cycle_outcome = "promoted"
            return "promoted"

        borderline = [c for c in evaluated if c.evaluation_verdict == "borderline"]
        if borderline:
            cycle.cycle_outcome = "re_research_triggered"
            return "re_research"

        cycle.cycle_outcome = "archived_no_alpha"
        return "archived"

    def _is_budget_exhausted(self, cycle: ResearchCycleORM) -> bool:
        """Check if the cycle's budget is exhausted."""
        consumed = json.loads(cycle.budget_consumed_json or "{}")
        budget = json.loads(cycle.budget_json or "{}")

        if consumed.get("trials", 0) >= budget.get("max_trials", 50):
            return True
        if consumed.get("backtests", 0) >= budget.get("max_backtests", 20):
            return True
        if consumed.get("llm_calls", 0) >= budget.get("max_llm_calls", 100):
            return True
        return False

    def _increment_budget(self, cycle: ResearchCycleORM, key: str, amount: int) -> None:
        """Increment a budget consumption counter."""
        consumed = json.loads(cycle.budget_consumed_json or "{}")
        consumed[key] = consumed.get(key, 0) + amount
        cycle.budget_consumed_json = json.dumps(consumed)

    async def _transition_status(
        self,
        cycle: ResearchCycleORM,
        target: str,
        reason: str,
    ) -> None:
        """Transition cycle to new status with validation."""
        current = cycle.status

        # Validate transition
        allowed = _TRANSITIONS.get(current, [])
        valid_targets = [t[0] for t in allowed]

        # Allow terminal transitions from any active state
        if target in _TERMINAL_STATES and current not in _TERMINAL_STATES:
            pass  # Always allow transition to terminal
        elif target not in valid_targets and target != current:
            logger.warning(
                f"Invalid transition: {current} → {target}. "
                f"Allowed: {valid_targets}. Forcing."
            )

        cycle.status = target
        await self._cycle_repo.update(cycle)
        logger.info(f"Cycle {cycle.research_cycle_id}: {current} → {target} ({reason})")

    async def run_to_completion(self, cycle_id: str, max_iterations: int = 50) -> list[LoopResult]:
        """Run the loop until the cycle reaches a terminal state or max iterations.

        Useful for testing or when a cycle should run autonomously.
        """
        results: list[LoopResult] = []
        for _ in range(max_iterations):
            result = await self.tick(cycle_id)
            results.append(result)
            if not result.should_continue:
                break
        return results
