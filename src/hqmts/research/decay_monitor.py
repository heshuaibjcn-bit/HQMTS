"""FactorDecayMonitorService -- monitors registered factors for decay.

Checks factor value distribution stability, strategy performance vs factor
predictions, and market regime changes that may invalidate factors.

FR-RES-019, SAD 24.10.4.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.types import FactorDiscoveryId, ResearchCycleId
from hqmts.db.models.research_cycle import FactorDiscoveryORM, ResearchCycleORM
from hqmts.db.repositories.research_cycle_repo import (
    FactorDiscoveryRepository,
    ResearchCycleRepository,
)


@dataclass
class DecayCheckResult:
    """Result of a single factor decay check."""

    factor_discovery_id: str
    factor_names: list[str]
    status: str  # healthy, degraded, decayed
    stability_score: float  # 0-1, 1 = perfectly stable
    distribution_drift: float  # 0-1, 0 = no drift
    performance_gap: float  # actual vs predicted, negative = underperforming
    regime_compatible: bool
    recommendation: str  # monitor, re_validate, trigger_research

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_discovery_id": self.factor_discovery_id,
            "factor_names": self.factor_names,
            "status": self.status,
            "stability_score": round(self.stability_score, 4),
            "distribution_drift": round(self.distribution_drift, 4),
            "performance_gap": round(self.performance_gap, 4),
            "regime_compatible": self.regime_compatible,
            "recommendation": self.recommendation,
        }


@dataclass
class DecayMonitorReport:
    """Aggregate decay monitoring report."""

    checked_count: int = 0
    healthy_count: int = 0
    degraded_count: int = 0
    decayed_count: int = 0
    factors: list[DecayCheckResult] = field(default_factory=list)
    triggered_cycle_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked_count": self.checked_count,
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "decayed_count": self.decayed_count,
            "factors": [f.to_dict() for f in self.factors],
            "triggered_cycle_ids": self.triggered_cycle_ids,
        }


# Thresholds for decay classification
_STABILITY_HEALTHY = 0.7
_STABILITY_DEGRADED = 0.4
_DRIFT_THRESHOLD = 0.3
_PERFORMANCE_GAP_THRESHOLD = -0.15


class FactorDecayMonitorService:
    """Monitor registered factors for decay and trigger re-research.

    FR-RES-019: Periodic monitoring of registered factors.
    SAD 24.10.4: Decay detection with automatic ResearchCycle trigger.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._discovery_repo = FactorDiscoveryRepository(session)
        self._cycle_repo = ResearchCycleRepository(session)

    async def check_all_registered(self) -> DecayMonitorReport:
        """Check all registered factors for decay.

        Returns aggregate report with per-factor results and any triggered cycles.
        """
        # Get all registered discoveries
        stmt = """
            SELECT * FROM factor_discoveries WHERE status = 'registered'
        """
        from sqlalchemy import text
        result = await self._session.execute(text(stmt))
        discoveries = result.fetchall()

        report = DecayMonitorReport(checked_count=len(discoveries))

        for row in discoveries:
            # Convert Row to dict-like access
            discovery = await self._discovery_repo.get_by_discovery_id(
                row.factor_discovery_id
            )
            if discovery is None:
                continue

            check = self._check_single(discovery)
            report.factors.append(check)

            if check.status == "healthy":
                report.healthy_count += 1
            elif check.status == "degraded":
                report.degraded_count += 1
            else:
                report.decayed_count += 1

            # Auto-trigger re-research for decayed factors
            if check.recommendation == "trigger_research":
                cycle_id = await self._trigger_re_research(discovery, check)
                if cycle_id:
                    report.triggered_cycle_ids.append(cycle_id)

        return report

    async def check_factor(self, discovery_id: str) -> DecayCheckResult | None:
        """Check a single factor for decay."""
        discovery = await self._discovery_repo.get_by_discovery_id(discovery_id)
        if discovery is None:
            return None
        return self._check_single(discovery)

    def _check_single(self, discovery: FactorDiscoveryORM) -> DecayCheckResult:
        """Run decay checks on a single factor discovery.

        In production, this would:
        1. Compare recent factor value distribution to validation baseline
        2. Compare strategy actual performance vs factor prediction
        3. Check if market regime changed since validation

        For now, uses heuristic scoring based on available metadata.
        """
        factor_names = json.loads(discovery.factor_names_json or "[]")

        # Heuristic: stability score based on confidence and significance
        stability = discovery.confidence
        if discovery.is_significant:
            stability = min(stability + 0.1, 1.0)

        # Heuristic: distribution drift placeholder
        # In production: compute KS test between current and baseline distributions
        drift = 0.0

        # Heuristic: performance gap placeholder
        # In production: compare live strategy Sharpe vs backtest Sharpe
        performance_gap = 0.0

        # Regime compatibility
        regime_compatible = True  # default unless proven otherwise

        # Classify status
        if stability >= _STABILITY_HEALTHY and drift < _DRIFT_THRESHOLD:
            status = "healthy"
            recommendation = "monitor"
        elif stability >= _STABILITY_DEGRADED:
            status = "degraded"
            recommendation = "re_validate"
        else:
            status = "decayed"
            recommendation = "trigger_research"

        if performance_gap < _PERFORMANCE_GAP_THRESHOLD:
            if status == "healthy":
                status = "degraded"
                recommendation = "re_validate"

        return DecayCheckResult(
            factor_discovery_id=discovery.factor_discovery_id,
            factor_names=factor_names,
            status=status,
            stability_score=stability,
            distribution_drift=drift,
            performance_gap=performance_gap,
            regime_compatible=regime_compatible,
            recommendation=recommendation,
        )

    async def _trigger_re_research(
        self,
        discovery: FactorDiscoveryORM,
        check: DecayCheckResult,
    ) -> str | None:
        """Create a new ResearchCycle triggered by factor decay detection."""
        cycle_id = ResearchCycleId(f"rc_{uuid.uuid4().hex[:12]}")

        signal = {
            "trigger": "factor_decay",
            "factor_discovery_id": discovery.factor_discovery_id,
            "factor_names": check.factor_names,
            "decay_status": check.status,
            "stability_score": check.stability_score,
            "recommendation": check.recommendation,
        }

        orm = ResearchCycleORM(
            research_cycle_id=cycle_id,
            title=f"衰减重新研究: {', '.join(check.factor_names[:3])}",
            opportunity_type="factor_decay",
            opportunity_signal_json=json.dumps(signal),
            status="opportunity_identified",
            source_strategy_instance_id="",
            triggered_by="decay_monitor",
            autonomy_level="level_2",
        )
        await self._cycle_repo.create(orm)
        return cycle_id

    async def get_status(self) -> dict[str, Any]:
        """Get current decay monitor status summary."""
        from sqlalchemy import text

        # Count by discovery status
        result = await self._session.execute(
            text("SELECT status, COUNT(*) as cnt FROM factor_discoveries GROUP BY status")
        )
        status_counts = {row.status: row.cnt for row in result.fetchall()}

        registered = status_counts.get("registered", 0)
        decayed = status_counts.get("expired", 0)

        return {
            "registered_factors": registered,
            "expired_factors": decayed,
            "status_distribution": status_counts,
            "monitor_active": True,
        }
