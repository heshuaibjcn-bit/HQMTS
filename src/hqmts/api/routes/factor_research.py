"""Factor research API routes (FR-RES-001~005).

Exposes factor registry, computation, AI agent chat (SSE),
governance dashboard, and research report endpoints.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.api.deps_auth import get_current_user
from hqmts.core.enums import Cycle
from hqmts.core.types import InstrumentId
from hqmts.db.repositories.bar_repo import BarRepository
from hqmts.research.factor import FactorCategory, FactorValue
from hqmts.research.governance import MultipleTestingGovernance
from hqmts.research.registry import create_default_registry

router = APIRouter(prefix="/factor-research", tags=["factor-research"])

# Module-level singleton instances
_registry = create_default_registry()
_governance = MultipleTestingGovernance(alpha=0.05, method="bonferroni", max_trials=1000)
_reports: dict[str, dict[str, Any]] = {}


# ── Pydantic models ────────────────────────────────────────────────────────────


class FactorInfoResponse(BaseModel):
    name: str
    category: str
    version: str
    description: str
    params: dict[str, Any]


class ComputeRequest(BaseModel):
    instrument_ids: list[str]
    factor_names: list[str]
    cycle: str = "1d"
    start_date: str  # ISO date string
    end_date: str  # ISO date string


class CorrelationRequest(BaseModel):
    instrument_id: str
    factor_names: list[str]
    cycle: str = "1d"
    start_date: str
    end_date: str


class AgentChatRequest(BaseModel):
    message: str
    context: dict[str, Any] | None = None


class ResearchTaskRequest(BaseModel):
    task_type: str  # correlation_analysis | regime_detection | hypothesis | anomaly
    instruments: list[str]
    factors: list[str]
    time_range_days: int = 250
    notes: str = ""


class ReportRequest(BaseModel):
    title: str
    factor_names: list[str]
    instrument_ids: list[str]
    time_range_days: int = 250
    include_governance: bool = True


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _factor_to_dict(factor: Any) -> dict[str, Any]:
    return {
        "name": factor.name,
        "category": factor.category.value,
        "version": factor.version,
        "description": factor.description,
        "params": factor.params,
    }


def _factor_value_to_dict(fv: FactorValue) -> dict[str, Any]:
    return {
        "factor_name": fv.factor_name,
        "instrument_id": fv.instrument_id,
        "value": fv.value,
        "timestamp": fv.timestamp,
        "version": fv.version,
        "metadata": fv.metadata,
    }


def _trial_to_dict(trial: Any) -> dict[str, Any]:
    return {
        "trial_id": trial.trial_id,
        "factor_name": trial.factor_name,
        "strategy_name": trial.strategy_name,
        "metric_name": trial.metric_name,
        "metric_value": trial.metric_value,
        "threshold": trial.threshold,
        "is_significant": trial.is_significant,
        "notes": trial.notes,
    }


def _governance_stats_to_dict(stats: Any) -> dict[str, Any]:
    return {
        "total_trials": stats.total_trials,
        "significant_count": stats.significant_count,
        "rejected_count": stats.rejected_count,
        "family_wise_error_rate": round(stats.family_wise_error_rate, 4),
        "false_discovery_rate": round(stats.false_discovery_rate, 4),
        "adjusted_threshold": _governance.get_adjusted_threshold(),
        "budget_remaining": _governance._max_trials - _governance.trial_count,
        "budget_total": _governance._max_trials,
    }


# ── Factor Registry ────────────────────────────────────────────────────────────


@router.get("/factors")
async def list_factors(
    category: str | None = Query(None, description="Filter by factor category"),
) -> dict:
    """List all registered factors (FR-RES-002)."""
    cat = FactorCategory(category) if category else None
    factors = _registry.list_factors(category=cat)
    return {
        "factors": [_factor_to_dict(f) for f in factors],
        "total": len(factors),
    }


@router.get("/factors/{name}")
async def get_factor(name: str) -> dict:
    """Get detail for a single factor (FR-RES-002)."""
    factor = _registry.get(name)
    if factor is None:
        raise HTTPException(status_code=404, detail=f"Factor '{name}' not found")
    return _factor_to_dict(factor)


# ── Factor Computation ─────────────────────────────────────────────────────────


@router.post("/compute")
async def compute_factors(
    req: ComputeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Compute factor values for given instruments and time range (FR-RES-001)."""
    try:
        cycle = Cycle(req.cycle)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid cycle: {req.cycle}")

    start = datetime.fromisoformat(req.start_date)
    end = datetime.fromisoformat(req.end_date)

    bar_repo = BarRepository(db)
    all_results: list[dict[str, Any]] = []

    for iid in req.instrument_ids:
        bars = await bar_repo.get_bars_by_instrument_cycle(
            instrument_id=InstrumentId(iid),
            cycle=cycle,
            start=start,
            end=end,
        )
        if not bars:
            continue

        for fname in req.factor_names:
            factor = _registry.get(fname)
            if factor is None:
                continue
            values = factor.compute(bars)
            all_results.extend(_factor_value_to_dict(v) for v in values)

    return {"values": all_results, "count": len(all_results)}


@router.post("/correlations")
async def compute_correlations(
    req: CorrelationRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Compute correlation matrix between factors (FR-RES-001)."""
    import numpy as np

    try:
        cycle = Cycle(req.cycle)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid cycle: {req.cycle}")

    start = datetime.fromisoformat(req.start_date)
    end = datetime.fromisoformat(req.end_date)

    bar_repo = BarRepository(db)
    bars = await bar_repo.get_bars_by_instrument_cycle(
        instrument_id=InstrumentId(req.instrument_id),
        cycle=cycle,
        start=start,
        end=end,
    )
    if not bars:
        return {"matrix": [], "factors": req.factor_names}

    # Compute each factor's values aligned by timestamp
    factor_series: dict[str, dict[str, float]] = {}
    timestamps: set[str] = set()

    for fname in req.factor_names:
        factor = _registry.get(fname)
        if factor is None:
            continue
        values = factor.compute(bars)
        series = {v.timestamp: v.value for v in values}
        factor_series[fname] = series
        timestamps.update(series.keys())

    if len(factor_series) < 2:
        return {"matrix": [], "factors": list(factor_series.keys())}

    sorted_ts = sorted(timestamps)
    names = list(factor_series.keys())
    n = len(names)

    # Build aligned arrays
    arrays: list[list[float]] = []
    for name in names:
        arr = [factor_series[name].get(ts, float("nan")) for ts in sorted_ts]
        arrays.append(arr)

    data = np.array(arrays)
    # Correlation matrix (handle NaN by using only overlapping timestamps)
    corr_matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            mask = ~np.isnan(data[i]) & ~np.isnan(data[j])
            if mask.sum() < 2:
                row.append(None)
            else:
                c = float(np.corrcoef(data[i][mask], data[j][mask])[0, 1])
                row.append(round(c, 4) if not np.isnan(c) else None)
        corr_matrix.append(row)

    return {"matrix": corr_matrix, "factors": names}


# ── AI Agent Chat (SSE) ────────────────────────────────────────────────────────


@router.post("/agent/chat")
async def agent_chat(
    req: AgentChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> StreamingResponse:
    """SSE-streamed AI research chat (FR-RES-003).

    Uses the factor research system prompt with optional context
    about selected instruments, factors, and time range.
    """
    from hqmts.llm.context_builder import build_factor_research_prompt
    from hqmts.llm.factory import LLMFactory

    settings = request.app.state.settings
    factory = LLMFactory(
        openai_api_key=getattr(settings, "openai_api_key", ""),
        ollama_base_url=getattr(settings, "ollama_base_url", "http://localhost:11434"),
    )

    # Use ollama for research by default, fall back to openai
    provider = getattr(settings, "default_research_provider", "ollama")
    adapter = factory.get_adapter("research", provider)

    system_prompt = build_factor_research_prompt(context=req.context)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.message},
    ]

    async def _stream():
        full_response: list[str] = []
        try:
            async for chunk in adapter.stream(messages):
                full_response.append(chunk)
                data = json.dumps({"type": "content", "content": chunk})
                yield f"data: {data}\n\n"
        except Exception as e:
            error_data = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {error_data}\n\n"
            return

        done_data = json.dumps({
            "type": "done",
            "full_response": "".join(full_response),
        })
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Research Tasks ──────────────────────────────────────────────────────────────


@router.post("/agent/research-task")
async def create_research_task(
    req: ResearchTaskRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Launch an autonomous research task through the governance chain (FR-RES-003/004)."""
    # Record as a governance trial
    trial = _governance.record_trial(
        factor_name=",".join(req.factors[:3]) + ("..." if len(req.factors) > 3 else ""),
        strategy_name=f"research_{req.task_type}",
        metric_name="sharpe_ratio",
        metric_value=0.0,
        threshold=_governance.get_adjusted_threshold(),
        notes=f"Instruments: {','.join(req.instruments)}, Range: {req.time_range_days}d. {req.notes}",
    )

    task_id = f"research_{uuid.uuid4().hex[:12]}"
    return {
        "task_id": task_id,
        "status": "submitted",
        "trial_id": trial.trial_id,
        "task_type": req.task_type,
        "instruments": req.instruments,
        "factors": req.factors,
        "time_range_days": req.time_range_days,
    }


# ── Governance Dashboard ───────────────────────────────────────────────────────


@router.get("/governance/stats")
async def get_governance_stats() -> dict:
    """Get governance statistics for the dashboard (FR-RES-004)."""
    stats = _governance.compute_stats()
    return _governance_stats_to_dict(stats)


@router.get("/governance/trials")
async def get_governance_trials(
    factor_name: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Get trial records for governance review (FR-RES-004)."""
    trials = _governance.get_trials(factor_name=factor_name)
    page = trials[offset : offset + limit]
    return {
        "trials": [_trial_to_dict(t) for t in page],
        "total": len(trials),
    }


# ── Research Reports ───────────────────────────────────────────────────────────


@router.post("/reports")
async def generate_report(
    req: ReportRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a structured research report (FR-RES-005)."""
    report_id = f"report_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()

    report: dict[str, Any] = {
        "report_id": report_id,
        "title": req.title,
        "created_at": now,
        "factor_names": req.factor_names,
        "instrument_ids": req.instrument_ids,
        "time_range_days": req.time_range_days,
        "sections": [],
    }

    # Factor analysis section
    factor_details = []
    for fname in req.factor_names:
        factor = _registry.get(fname)
        if factor:
            factor_details.append(_factor_to_dict(factor))
    report["sections"].append({
        "type": "factor_analysis",
        "title": "因子分析",
        "factors": factor_details,
    })

    # Governance section
    if req.include_governance:
        stats = _governance.compute_stats()
        report["sections"].append({
            "type": "governance",
            "title": "治理统计",
            "stats": _governance_stats_to_dict(stats),
        })

    _reports[report_id] = report
    return report


@router.get("/reports/{report_id}")
async def get_report(report_id: str) -> dict:
    """Retrieve a previously generated report (FR-RES-005)."""
    report = _reports.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report


# ═══════════════════════════════════════════════════════════════════════════════
# Research Project Workflow (FR-RES-006~013)
# ═══════════════════════════════════════════════════════════════════════════════


class CreateProjectRequest(BaseModel):
    title: str
    research_question: str
    instrument_ids: list[str] = []
    factor_categories: list[str] = []
    time_range_start: str = ""
    time_range_end: str = ""
    cycle: str = "1d"
    trial_budget: int = 100
    mode: str = "collaborative"


class CreateHypothesisRequest(BaseModel):
    prediction: str = ""
    factor_names: list[str] = []
    target_metric: str = "sharpe_ratio"
    expected_effect: str = "positive"
    expected_magnitude: float = 0.0
    instrument_scope: list[str] = []
    ai_rationale: str = ""
    confidence: float = 0.5
    created_by: str = "ai"


class UpdateHypothesisRequest(BaseModel):
    status: str  # accepted | rejected
    human_rationale: str = ""


class DesignTrialPlanRequest(BaseModel):
    hypothesis_id: str
    factor_combination: list[str] = []
    instruments: list[str] = []
    train_period_start: str = ""
    train_period_end: str = ""
    test_period_start: str = ""
    test_period_end: str = ""
    metric_name: str = "sharpe_ratio"
    metric_threshold: float = 0.0


class ProjectChatRequest(BaseModel):
    message: str
    context: dict[str, Any] | None = None


def _get_orchestrator(db: AsyncSession) -> Any:
    from hqmts.research.orchestrator import ResearchOrchestrator
    return ResearchOrchestrator(db)


# ── Project CRUD ──────────────────────────────────────────────────────────────


@router.post("/projects")
async def create_project(
    req: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Create a new research project (FR-RES-006)."""
    orch = _get_orchestrator(db)
    project = await orch.create_project(
        title=req.title,
        research_question=req.research_question,
        instrument_ids=req.instrument_ids,
        factor_categories=req.factor_categories,
        time_range_start=req.time_range_start,
        time_range_end=req.time_range_end,
        cycle=req.cycle,
        trial_budget=req.trial_budget,
        mode=req.mode,
        created_by=getattr(user, "username", ""),
    )
    return project.to_dict()


@router.get("/projects")
async def list_projects(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List research projects (FR-RES-006)."""
    orch = _get_orchestrator(db)
    projects, total = await orch.list_projects(status=status, limit=limit, offset=offset)
    return {
        "projects": [p.to_dict() for p in projects],
        "total": total,
    }


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get project detail with linked artifacts (FR-RES-006)."""
    orch = _get_orchestrator(db)
    project = await orch.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = project.to_dict()

    # Include hypotheses and trial plans
    hypotheses = await orch.list_hypotheses(project_id)
    result["hypotheses"] = [h.to_dict() for h in hypotheses]

    trial_plans = await orch.list_trial_plans(project_id)
    result["trial_plans"] = [t.to_dict() for t in trial_plans]

    return result


@router.post("/projects/{project_id}/advance")
async def advance_project_stage(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Advance project to the next lifecycle stage (FR-RES-006)."""
    orch = _get_orchestrator(db)
    try:
        project = await orch.advance_stage(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return project.to_dict()


@router.post("/projects/{project_id}/cancel")
async def cancel_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Cancel a research project (FR-RES-006)."""
    orch = _get_orchestrator(db)
    try:
        project = await orch.cancel_project(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return project.to_dict()


@router.post("/projects/{project_id}/rollback")
async def rollback_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Roll back from validating to executing (FR-RES-006)."""
    orch = _get_orchestrator(db)
    try:
        project = await orch.rollback_to_executing(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return project.to_dict()


# ── Hypothesis CRUD ───────────────────────────────────────────────────────────


@router.post("/projects/{project_id}/hypotheses")
async def create_hypothesis(
    project_id: str,
    req: CreateHypothesisRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Create or AI-generate a hypothesis (FR-RES-008)."""
    orch = _get_orchestrator(db)
    hypothesis = await orch.create_hypothesis(
        project_id=project_id,
        prediction=req.prediction,
        factor_names=req.factor_names,
        target_metric=req.target_metric,
        expected_effect=req.expected_effect,
        expected_magnitude=req.expected_magnitude,
        instrument_scope=req.instrument_scope,
        ai_rationale=req.ai_rationale,
        confidence=req.confidence,
        created_by=req.created_by,
    )
    return hypothesis.to_dict()


@router.get("/projects/{project_id}/hypotheses")
async def list_hypotheses(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List hypotheses for a project (FR-RES-008)."""
    orch = _get_orchestrator(db)
    hypotheses = await orch.list_hypotheses(project_id)
    return {
        "hypotheses": [h.to_dict() for h in hypotheses],
        "total": len(hypotheses),
    }


@router.patch("/hypotheses/{hypothesis_id}")
async def update_hypothesis(
    hypothesis_id: str,
    req: UpdateHypothesisRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Accept, reject, or modify a hypothesis (FR-RES-008)."""
    orch = _get_orchestrator(db)
    hypothesis = await orch.update_hypothesis_status(
        hypothesis_id=hypothesis_id,
        status=req.status,
        human_rationale=req.human_rationale,
    )
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return hypothesis.to_dict()


# ── Trial Plan CRUD ───────────────────────────────────────────────────────────


@router.post("/hypotheses/{hypothesis_id}/trial-plan")
async def design_trial_plan(
    hypothesis_id: str,
    req: DesignTrialPlanRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Design a pre-registered trial plan for a hypothesis (FR-RES-009)."""
    orch = _get_orchestrator(db)
    # Look up project_id from hypothesis
    from hqmts.db.repositories.research_repo import HypothesisRepository
    hyp_repo = HypothesisRepository(db)
    hyp_orm = await hyp_repo.get_by_hypothesis_id(hypothesis_id)
    if hyp_orm is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    plan = await orch.create_trial_plan(
        project_id=hyp_orm.research_project_id,
        hypothesis_id=hypothesis_id,
        factor_combination=req.factor_combination,
        instruments=req.instruments,
        train_period_start=req.train_period_start,
        train_period_end=req.train_period_end,
        test_period_start=req.test_period_start,
        test_period_end=req.test_period_end,
        metric_name=req.metric_name,
        metric_threshold=req.metric_threshold,
    )
    return plan.to_dict()


@router.post("/trial-plans/{trial_plan_id}/execute")
async def execute_trial_plan(
    trial_plan_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Execute a pre-registered trial plan (FR-RES-009)."""
    orch = _get_orchestrator(db)
    try:
        result = await orch.execute_trial(trial_plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result.model_dump()


@router.post("/trial-plans/{trial_plan_id}/validate")
async def validate_trial_plan(
    trial_plan_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Validate a completed trial plan with governance stats (FR-RES-010)."""
    orch = _get_orchestrator(db)
    from hqmts.db.repositories.research_repo import TrialPlanRepository
    repo = TrialPlanRepository(db)
    orm = await repo.get_by_trial_id(trial_plan_id)
    if orm is None:
        raise HTTPException(status_code=404, detail="Trial plan not found")

    stats = await orch.get_governance_stats(orm.research_project_id)
    return {
        "trial_plan_id": trial_plan_id,
        "status": orm.status,
        "governance": stats,
    }


# ── Project-scoped AI Chat (SSE) ─────────────────────────────────────────────


@router.post("/projects/{project_id}/explore")
async def project_explore_chat(
    project_id: str,
    req: ProjectChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> StreamingResponse:
    """SSE-streamed exploration chat for a project (FR-RES-007)."""
    from hqmts.llm.context_builder import build_research_project_prompt
    from hqmts.llm.factory import LLMFactory

    orch = _get_orchestrator(db)
    project = await orch.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    settings = request.app.state.settings
    factory = LLMFactory(
        openai_api_key=getattr(settings, "openai_api_key", ""),
        ollama_base_url=getattr(settings, "ollama_base_url", "http://localhost:11434"),
    )
    provider = getattr(settings, "default_research_provider", "ollama")
    adapter = factory.get_adapter("research", provider)

    project_ctx = {
        "current_stage": project.current_stage,
        "research_question": project.research_question,
        "title": project.title,
        "instruments": project.instrument_ids,
        "mode": project.mode.value,
    }
    system_prompt = build_research_project_prompt(project_ctx)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.message},
    ]

    async def _stream():
        full_response: list[str] = []
        try:
            async for chunk in adapter.stream(messages):
                full_response.append(chunk)
                data = json.dumps({"type": "content", "content": chunk})
                yield f"data: {data}\n\n"
        except Exception as e:
            error_data = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {error_data}\n\n"
            return

        done_data = json.dumps({
            "type": "done",
            "full_response": "".join(full_response),
        })
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Project-scoped Governance ─────────────────────────────────────────────────


@router.get("/projects/{project_id}/governance")
async def get_project_governance(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get governance stats for a specific project (FR-RES-010)."""
    orch = _get_orchestrator(db)
    return await orch.get_governance_stats(project_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Autonomous Research Cycles (FR-RES-014~020, FR-STR-006~012)
# ═══════════════════════════════════════════════════════════════════════════════


class CreateCycleRequest(BaseModel):
    title: str
    opportunity_type: str = "human_initiated"
    opportunity_signal_json: dict[str, Any] = {}
    research_question: str = ""
    instrument_ids: list[str] = []
    factor_categories: list[str] = []
    autonomy_level: str = "level_2"


class ApprovePaperRequest(BaseModel):
    notes: str = ""


# Valid state transitions for ResearchCycle (SAD 15)
_CYCLE_TRANSITIONS: dict[str, set[str]] = {
    "opportunity_identified": {"researching", "canceled"},
    "researching": {"factor_validated", "researching", "canceled", "failed"},
    "factor_validated": {"synthesizing", "canceled"},
    "synthesizing": {"backtesting", "canceled", "failed"},
    "backtesting": {"evaluating", "canceled", "failed"},
    "evaluating": {"promoted", "archived", "re_research", "canceled"},
    "re_research": {"researching", "canceled", "failed"},
}


def _cycle_to_dict(orm: Any) -> dict[str, Any]:
    """Convert ResearchCycleORM to dict."""
    import json as _json
    return {
        "research_cycle_id": orm.research_cycle_id,
        "title": orm.title,
        "opportunity_type": orm.opportunity_type,
        "opportunity_signal": _json.loads(orm.opportunity_signal_json),
        "status": orm.status,
        "research_project_id": orm.research_project_id,
        "budget": _json.loads(orm.budget_json),
        "budget_consumed": _json.loads(orm.budget_consumed_json),
        "factor_discovery_ids": _json.loads(orm.factor_discovery_ids_json),
        "strategy_candidate_ids": _json.loads(orm.strategy_candidate_ids_json),
        "autonomy_level": orm.autonomy_level,
        "cycle_outcome": orm.cycle_outcome,
        "outcome_reason": orm.outcome_reason,
        "source_strategy_instance_id": orm.source_strategy_instance_id,
        "triggered_by": orm.triggered_by,
        "agent_task_id": orm.agent_task_id,
        "created_at": orm.created_at.isoformat() if orm.created_at else None,
        "updated_at": orm.updated_at.isoformat() if orm.updated_at else None,
    }


def _discovery_to_dict(orm: Any) -> dict[str, Any]:
    """Convert FactorDiscoveryORM to dict."""
    import json as _json
    return {
        "factor_discovery_id": orm.factor_discovery_id,
        "research_cycle_id": orm.research_cycle_id,
        "research_project_id": orm.research_project_id,
        "factor_names": _json.loads(orm.factor_names_json),
        "factor_combination": orm.factor_combination,
        "discovery_type": orm.discovery_type,
        "description": orm.description,
        "hypothesis_id": orm.hypothesis_id,
        "trial_plan_id": orm.trial_plan_id,
        "metric_value": orm.metric_value,
        "adjusted_alpha": orm.adjusted_alpha,
        "is_significant": bool(orm.is_significant),
        "confidence": orm.confidence,
        "market_regime": orm.market_regime,
        "instrument_scope": _json.loads(orm.instrument_scope_json),
        "status": orm.status,
        "created_at": orm.created_at.isoformat() if orm.created_at else None,
    }


def _candidate_to_dict(orm: Any) -> dict[str, Any]:
    """Convert StrategyCandidateORM to dict."""
    import json as _json
    return {
        "strategy_candidate_id": orm.strategy_candidate_id,
        "research_cycle_id": orm.research_cycle_id,
        "factor_discovery_ids": _json.loads(orm.factor_discovery_ids_json),
        "source_factors": _json.loads(orm.source_factors_json),
        "strategy_template_name": orm.strategy_template_name,
        "strategy_params": _json.loads(orm.strategy_params_json),
        "param_ranges": _json.loads(orm.param_ranges_json),
        "ai_rationale": orm.ai_rationale,
        "signal_logic_description": orm.signal_logic_description,
        "status": orm.status,
        "backtest_sharpe": orm.backtest_sharpe,
        "backtest_return": orm.backtest_return,
        "backtest_drawdown": orm.backtest_drawdown,
        "backtest_trades": orm.backtest_trades,
        "evaluation_score": orm.evaluation_score,
        "evaluation_verdict": orm.evaluation_verdict,
        "created_at": orm.created_at.isoformat() if orm.created_at else None,
    }


@router.post("/cycles")
async def create_cycle(
    req: CreateCycleRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Create a new research cycle (FR-RES-014)."""
    import json as _json
    from hqmts.db.models.research_cycle import ResearchCycleORM
    from hqmts.db.repositories.research_cycle_repo import ResearchCycleRepository

    cycle_id = f"rc_{uuid.uuid4().hex[:12]}"
    repo = ResearchCycleRepository(db)

    # Optionally create a linked research project
    project_id: str | None = None
    if req.research_question:
        orch = _get_orchestrator(db)
        project = await orch.create_project(
            title=req.title,
            research_question=req.research_question,
            instrument_ids=req.instrument_ids,
            factor_categories=req.factor_categories,
            mode="ai_autonomous",
            created_by=getattr(user, "username", "system"),
        )
        project_id = project.research_project_id

    cycle = ResearchCycleORM(
        research_cycle_id=cycle_id,
        title=req.title,
        opportunity_type=req.opportunity_type,
        opportunity_signal_json=_json.dumps(req.opportunity_signal_json),
        research_project_id=project_id,
        autonomy_level=req.autonomy_level,
        triggered_by=getattr(user, "username", "system"),
        budget_json=_json.dumps({
            "max_trials": 100,
            "max_llm_calls": 50,
            "max_backtests": 20,
            "max_duration_hours": 24,
        }),
        budget_consumed_json=_json.dumps({
            "trials": 0,
            "llm_calls": 0,
            "backtests": 0,
        }),
    )
    await repo.create(cycle)
    await db.commit()
    return _cycle_to_dict(cycle)


@router.get("/cycles")
async def list_cycles(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List research cycles (FR-RES-014)."""
    from hqmts.db.repositories.research_cycle_repo import ResearchCycleRepository

    repo = ResearchCycleRepository(db)
    if status:
        cycles = await repo.list_by_status(status, limit=limit, offset=offset)
        total = await repo.count(filters={"status": status})
    else:
        cycles = await repo.get_many(limit=limit, offset=offset)
        total = await repo.count()

    return {
        "cycles": [_cycle_to_dict(c) for c in cycles],
        "total": total,
    }


@router.get("/cycles/{cycle_id}")
async def get_cycle(
    cycle_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get cycle detail with discoveries and candidates (FR-RES-014)."""
    import json as _json
    from hqmts.db.repositories.research_cycle_repo import (
        FactorDiscoveryRepository,
        ResearchCycleRepository,
        StrategyCandidateRepository,
    )

    cycle_repo = ResearchCycleRepository(db)
    cycle = await cycle_repo.get_by_cycle_id(cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")

    result = _cycle_to_dict(cycle)

    discovery_repo = FactorDiscoveryRepository(db)
    discoveries = await discovery_repo.list_by_cycle(cycle_id)
    result["discoveries"] = [_discovery_to_dict(d) for d in discoveries]

    candidate_repo = StrategyCandidateRepository(db)
    candidates = await candidate_repo.list_by_cycle(cycle_id)
    result["candidates"] = [_candidate_to_dict(c) for c in candidates]

    return result


@router.post("/cycles/{cycle_id}/cancel")
async def cancel_cycle(
    cycle_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Cancel a research cycle (FR-RES-014)."""
    from hqmts.db.repositories.research_cycle_repo import ResearchCycleRepository

    repo = ResearchCycleRepository(db)
    cycle = await repo.get_by_cycle_id(cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")

    allowed = _CYCLE_TRANSITIONS.get(cycle.status, set())
    if "canceled" not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot cancel cycle in '{cycle.status}' state")

    cycle.status = "canceled"
    cycle.cycle_outcome = "canceled"
    cycle.outcome_reason = f"Cancelled by {getattr(user, 'username', 'user')}"
    await repo.update(cycle)
    await db.commit()
    return _cycle_to_dict(cycle)


@router.get("/cycles/{cycle_id}/discoveries")
async def list_cycle_discoveries(
    cycle_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List factor discoveries for a cycle (FR-RES-016)."""
    from hqmts.db.repositories.research_cycle_repo import (
        FactorDiscoveryRepository,
        ResearchCycleRepository,
    )

    cycle_repo = ResearchCycleRepository(db)
    cycle = await cycle_repo.get_by_cycle_id(cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")

    discovery_repo = FactorDiscoveryRepository(db)
    discoveries = await discovery_repo.list_by_cycle(cycle_id)
    return {
        "discoveries": [_discovery_to_dict(d) for d in discoveries],
        "total": len(discoveries),
    }


@router.get("/cycles/{cycle_id}/candidates")
async def list_cycle_candidates(
    cycle_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List strategy candidates for a cycle (FR-STR-006)."""
    from hqmts.db.repositories.research_cycle_repo import (
        ResearchCycleRepository,
        StrategyCandidateRepository,
    )

    cycle_repo = ResearchCycleRepository(db)
    cycle = await cycle_repo.get_by_cycle_id(cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")

    candidate_repo = StrategyCandidateRepository(db)
    candidates = await candidate_repo.list_by_cycle(cycle_id)
    return {
        "candidates": [_candidate_to_dict(c) for c in candidates],
        "total": len(candidates),
    }


@router.post("/candidates/{candidate_id}/approve-paper")
async def approve_candidate_paper(
    candidate_id: str,
    req: ApprovePaperRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Approve strategy candidate for Paper deployment (FR-STR-010)."""
    from hqmts.db.repositories.research_cycle_repo import StrategyCandidateRepository

    repo = StrategyCandidateRepository(db)
    candidate = await repo.get_by_candidate_id(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.status = "promoted"
    candidate.evaluation_verdict = "promoted"
    await repo.update(candidate)
    await db.commit()
    return _candidate_to_dict(candidate)


@router.post("/candidates/{candidate_id}/reject")
async def reject_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Reject a strategy candidate (FR-STR-009)."""
    from hqmts.db.repositories.research_cycle_repo import StrategyCandidateRepository

    repo = StrategyCandidateRepository(db)
    candidate = await repo.get_by_candidate_id(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.status = "rejected"
    candidate.evaluation_verdict = "rejected"
    await repo.update(candidate)
    await db.commit()
    return _candidate_to_dict(candidate)


@router.get("/decay-monitor/status")
async def get_decay_monitor_status(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get factor decay monitoring status (FR-RES-019)."""
    from hqmts.research.decay_monitor import FactorDecayMonitorService

    monitor = FactorDecayMonitorService(db)
    return await monitor.get_status()


@router.post("/cycles/{cycle_id}/synthesize")
async def synthesize_cycle_candidates(
    cycle_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Trigger strategy candidate synthesis for a cycle (FR-STR-006)."""
    from hqmts.db.repositories.research_cycle_repo import ResearchCycleRepository
    from hqmts.research.bridge import FactorStrategyBridgeService

    cycle_repo = ResearchCycleRepository(db)
    cycle = await cycle_repo.get_by_cycle_id(cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Cycle not found")

    bridge = FactorStrategyBridgeService(db)
    candidates = await bridge.synthesize_candidates(
        cycle_id,
        cycle.research_project_id or "",
    )

    # Update cycle with new candidate IDs
    cand_ids = [c.strategy_candidate_id for c in candidates]
    existing_ids = json.loads(cycle.strategy_candidate_ids_json or "[]")
    all_ids = existing_ids + cand_ids
    cycle.strategy_candidate_ids_json = json.dumps(all_ids)
    await cycle_repo.update(cycle)
    await db.commit()

    return {
        "candidates": [_candidate_to_dict(c) for c in candidates],
        "total": len(candidates),
    }


@router.post("/candidates/{candidate_id}/evaluate")
async def evaluate_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Evaluate a strategy candidate with composite scoring (FR-STR-009)."""
    from hqmts.research.bridge import FactorStrategyBridgeService

    bridge = FactorStrategyBridgeService(db)
    try:
        candidate = await bridge.evaluate_candidate(candidate_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await db.commit()
    return _candidate_to_dict(candidate)


@router.post("/cycles/{cycle_id}/tick")
async def cycle_tick(
    cycle_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Execute one loop iteration for a cycle (SAD 24.10.1)."""
    from hqmts.research.autonomous_loop import AutonomousResearchLoop

    loop = AutonomousResearchLoop(db)
    result = await loop.tick(cycle_id)
    await db.commit()
    return {
        "cycle_id": result.cycle_id,
        "previous_status": result.previous_status,
        "current_status": result.current_status,
        "action_taken": result.action_taken,
        "message": result.message,
        "should_continue": result.should_continue,
        "requires_approval": result.requires_approval,
        "artifacts_created": result.artifacts_created,
    }


@router.post("/cycles/{cycle_id}/run")
async def cycle_run_to_completion(
    cycle_id: str,
    max_iterations: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Run a cycle to completion autonomously (SAD 24.10.1)."""
    from hqmts.research.autonomous_loop import AutonomousResearchLoop

    loop = AutonomousResearchLoop(db)
    results = await loop.run_to_completion(cycle_id, max_iterations=max_iterations)
    await db.commit()

    return {
        "cycle_id": cycle_id,
        "iterations": len(results),
        "final_status": results[-1].current_status if results else None,
        "steps": [
            {
                "previous_status": r.previous_status,
                "current_status": r.current_status,
                "action": r.action_taken,
                "message": r.message,
            }
            for r in results
        ],
    }


@router.post("/decay-monitor/check")
async def run_decay_check(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Run full factor decay check (FR-RES-019)."""
    from hqmts.research.decay_monitor import FactorDecayMonitorService

    monitor = FactorDecayMonitorService(db)
    report = await monitor.check_all_registered()
    await db.commit()
    return report.to_dict()
