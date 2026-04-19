"""FactorStrategyBridgeService -- translates FactorDiscovery into StrategyCandidate.

Maps factor patterns to strategy templates, generates parameter suggestions
from factor characteristics, and defines parameter search ranges.

SAD 24.10.3, FR-STR-006~008.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.types import FactorDiscoveryId, StrategyCandidateId
from hqmts.db.models.research_cycle import FactorDiscoveryORM, StrategyCandidateORM
from hqmts.db.repositories.research_cycle_repo import (
    FactorDiscoveryRepository,
    StrategyCandidateRepository,
)


# ── Factor pattern → Strategy template mapping ──────────────────────────────────

TEMPLATE_MAP: dict[str, str] = {
    "trend": "trend_following",
    "momentum": "trend_following",
    "mean_reversion": "mean_reversion",
    "overbought_oversold": "mean_reversion",
    "volatility": "breakout",
    "breakout": "breakout",
    "volume": "volume_profile",
    "sentiment": "contrarian",
}

REGIME_TEMPLATE_PRIORITY: dict[str, list[str]] = {
    "trending": ["trend_following", "breakout"],
    "mean_reverting": ["mean_reversion", "contrarian"],
    "volatile": ["breakout", "volume_profile"],
}

# Default parameter templates per strategy type
PARAM_TEMPLATES: dict[str, dict[str, Any]] = {
    "trend_following": {
        "lookback": 20,
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.06,
        "position_size": 0.1,
    },
    "mean_reversion": {
        "lookback": 14,
        "entry_zscore": 2.0,
        "exit_zscore": 0.5,
        "position_size": 0.08,
    },
    "breakout": {
        "lookback": 20,
        "atr_multiplier": 2.0,
        "stop_loss_atr": 1.5,
        "position_size": 0.1,
    },
    "volume_profile": {
        "volume_threshold": 1.5,
        "lookback": 10,
        "position_size": 0.08,
    },
    "contrarian": {
        "lookback": 5,
        "reversal_threshold": 0.03,
        "position_size": 0.06,
    },
}


def _classify_factor_pattern(factor_names: list[str]) -> str:
    """Classify a set of factor names into a primary pattern."""
    names_lower = " ".join(n.lower() for n in factor_names)
    for keyword, pattern in [
        ("trend", "trend"),
        ("momentum", "momentum"),
        ("mean_rev", "mean_reversion"),
        ("overbought", "overbought_oversold"),
        ("oversold", "overbought_oversold"),
        ("volatility", "volatility"),
        ("atr", "volatility"),
        ("breakout", "breakout"),
        ("volume", "volume"),
        ("sentiment", "sentiment"),
    ]:
        if keyword in names_lower:
            return pattern
    return "trend"  # default


def _select_template(
    factor_pattern: str,
    market_regime: str = "",
    all_factors: list[str] | None = None,
) -> str:
    """Select strategy template based on factor pattern and market regime."""
    # If regime is known, prefer regime-specific templates
    if market_regime and market_regime in REGIME_TEMPLATE_PRIORITY:
        # Check if any priority template matches the factor pattern
        regime_templates = REGIME_TEMPLATE_PRIORITY[market_regime]
        pattern_template = TEMPLATE_MAP.get(factor_pattern, "trend_following")
        if pattern_template in regime_templates:
            return pattern_template
        # Fall back to highest priority regime template
        return regime_templates[0]

    return TEMPLATE_MAP.get(factor_pattern, "trend_following")


def _suggest_params(
    template_name: str,
    discoveries: list[FactorDiscoveryORM],
) -> dict[str, Any]:
    """Generate parameter suggestions based on factor characteristics."""
    base = PARAM_TEMPLATES.get(template_name, PARAM_TEMPLATES["trend_following"]).copy()

    # Adjust lookback based on factor confidence and metric value
    if discoveries:
        avg_confidence = sum(d.confidence for d in discoveries) / len(discoveries)
        avg_metric = sum(abs(d.metric_value) for d in discoveries) / len(discoveries)

        # Higher confidence → longer lookback (more stable signal)
        if avg_confidence > 0.8 and "lookback" in base:
            base["lookback"] = int(base["lookback"] * 1.25)

        # Higher metric → can use tighter stops
        if avg_metric > 1.5:
            if "stop_loss_pct" in base:
                base["stop_loss_pct"] = round(base["stop_loss_pct"] * 0.8, 4)
            if "stop_loss_atr" in base:
                base["stop_loss_atr"] = round(base["stop_loss_atr"] * 0.8, 4)

    return base


def _compute_param_ranges(params: dict[str, Any]) -> dict[str, list]:
    """Compute parameter search ranges: center ±50%."""
    ranges: dict[str, list] = {}
    for key, value in params.items():
        if isinstance(value, int):
            lo = max(1, int(value * 0.5))
            hi = int(value * 1.5)
            ranges[key] = [lo, hi]
        elif isinstance(value, float):
            lo = round(value * 0.5, 6)
            hi = round(value * 1.5, 6)
            ranges[key] = [lo, hi]
        # Skip non-numeric params
    return ranges


class FactorStrategyBridgeService:
    """Translate validated factor discoveries into strategy candidates.

    FR-STR-006: Strategy candidate generation from FactorDiscovery.
    FR-STR-007: Factor-enhanced signal generation.
    FR-STR-008: Autonomous parameter scanning ranges.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._discovery_repo = FactorDiscoveryRepository(session)
        self._candidate_repo = StrategyCandidateRepository(session)

    async def synthesize_candidates(
        self,
        cycle_id: str,
        research_project_id: str = "",
    ) -> list[StrategyCandidateORM]:
        """Generate strategy candidates from all significant discoveries in a cycle.

        Returns the list of newly created StrategyCandidateORM objects.
        """
        discoveries = await self._discovery_repo.list_significant_by_cycle(cycle_id)
        if not discoveries:
            return []

        # Group discoveries by similar factor pattern
        groups = self._group_discoveries(discoveries)

        candidates: list[StrategyCandidateORM] = []
        for pattern, group_discs in groups.items():
            # Collect all factor names from this group
            all_factor_names: list[str] = []
            for d in group_discs:
                all_factor_names.extend(json.loads(d.factor_names_json or "[]"))

            # Get dominant regime from discoveries
            regimes = [d.market_regime for d in group_discs if d.market_regime]
            regime = max(set(regimes), key=regimes.count) if regimes else ""

            template = _select_template(pattern, regime, all_factor_names)
            params = _suggest_params(template, group_discs)
            ranges = _compute_param_ranges(params)

            discovery_ids = [d.factor_discovery_id for d in group_discs]

            candidate_id = StrategyCandidateId(f"sc_{uuid.uuid4().hex[:12]}")
            orm = StrategyCandidateORM(
                strategy_candidate_id=candidate_id,
                research_cycle_id=cycle_id,
                factor_discovery_ids_json=json.dumps(discovery_ids),
                source_factors_json=json.dumps(list(set(all_factor_names))),
                strategy_template_name=template,
                strategy_params_json=json.dumps(params),
                param_ranges_json=json.dumps(ranges),
                ai_rationale=self._build_rationale(pattern, template, group_discs, regime),
                signal_logic_description=self._build_signal_logic(template, all_factor_names),
                status="generated",
            )
            await self._candidate_repo.create(orm)
            candidates.append(orm)

        return candidates

    def _group_discoveries(
        self, discoveries: list[FactorDiscoveryORM]
    ) -> dict[str, list[FactorDiscoveryORM]]:
        """Group discoveries by classified factor pattern."""
        groups: dict[str, list[FactorDiscoveryORM]] = {}
        for d in discoveries:
            names = json.loads(d.factor_names_json or "[]")
            pattern = _classify_factor_pattern(names)
            groups.setdefault(pattern, []).append(d)
        return groups

    def _build_rationale(
        self,
        pattern: str,
        template: str,
        discoveries: list[FactorDiscoveryORM],
        regime: str,
    ) -> str:
        """Build AI rationale string for why this template was chosen."""
        factor_names = []
        for d in discoveries:
            factor_names.extend(json.loads(d.factor_names_json or "[]"))
        unique_factors = list(set(factor_names))

        avg_metric = sum(abs(d.metric_value) for d in discoveries) / len(discoveries)
        avg_conf = sum(d.confidence for d in discoveries) / len(discoveries)

        parts = [
            f"因子模式: {pattern} → 模板: {template}",
            f"源因子: {', '.join(unique_factors[:5])}",
            f"平均指标值: {avg_metric:.3f}, 平均置信度: {avg_conf:.0%}",
        ]
        if regime:
            parts.append(f"适用制度: {regime}")
        parts.append(f"基于 {len(discoveries)} 个显著因子发现生成")
        return "; ".join(parts)

    def _build_signal_logic(self, template: str, factor_names: list[str]) -> str:
        """Build human-readable signal logic description."""
        unique = list(set(factor_names))[:5]
        return f"使用因子 [{', '.join(unique)}] 作为 {template} 策略的信号输入"

    async def evaluate_candidate(
        self,
        candidate_id: str,
        sharpe_threshold: float = 0.8,
        max_drawdown: float = 0.10,
        min_trades: int = 30,
    ) -> StrategyCandidateORM:
        """Evaluate a strategy candidate after backtest results are available.

        FR-STR-009: Composite scoring with risk-adjusted return, drawdown control,
        parameter stability, and governance compliance.

        Updates the candidate's evaluation_score, evaluation_verdict, and status.
        """
        orm = await self._candidate_repo.get_by_candidate_id(candidate_id)
        if orm is None:
            raise ValueError(f"Candidate {candidate_id} not found")

        # Compute composite score
        score = self._compute_score(orm, sharpe_threshold, max_drawdown, min_trades)
        orm.evaluation_score = score

        # Determine verdict
        if (
            orm.backtest_sharpe is not None
            and orm.backtest_sharpe >= sharpe_threshold
            and orm.backtest_drawdown is not None
            and orm.backtest_drawdown <= max_drawdown
            and orm.backtest_trades is not None
            and orm.backtest_trades >= min_trades
        ):
            orm.evaluation_verdict = "promote"
        elif orm.backtest_sharpe is not None and orm.backtest_sharpe >= sharpe_threshold * 0.5:
            orm.evaluation_verdict = "borderline"
        else:
            orm.evaluation_verdict = "reject"

        orm.status = "evaluated"
        await self._candidate_repo.update(orm)
        return orm

    def _compute_score(
        self,
        candidate: StrategyCandidateORM,
        sharpe_threshold: float,
        max_drawdown: float,
        min_trades: int,
    ) -> float:
        """Compute composite evaluation score (0-1)."""
        score = 0.0
        weights = {"sharpe": 0.35, "drawdown": 0.25, "trades": 0.15, "return": 0.25}

        # Sharpe component
        if candidate.backtest_sharpe is not None:
            sharpe_ratio = min(candidate.backtest_sharpe / (sharpe_threshold * 2), 1.0)
            score += weights["sharpe"] * sharpe_ratio

        # Drawdown component (lower is better)
        if candidate.backtest_drawdown is not None:
            dd_score = max(0, 1.0 - candidate.backtest_drawdown / max_drawdown)
            score += weights["drawdown"] * dd_score

        # Trade count component
        if candidate.backtest_trades is not None:
            trade_score = min(candidate.backtest_trades / (min_trades * 3), 1.0)
            score += weights["trades"] * trade_score

        # Return component
        if candidate.backtest_return is not None:
            ret_score = min(max(candidate.backtest_return, 0) / 0.3, 1.0)
            score += weights["return"] * ret_score

        return round(score, 4)
