"""Paper-to-Live readiness assessment framework (SAD 25).

Evaluates whether a strategy is ready to graduate from Paper trading
to Live trading based on a checklist of readiness criteria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ReadinessCategory(str, Enum):
    """Categories of readiness checks."""

    PERFORMANCE = "performance"
    RISK = "risk"
    STABILITY = "stability"
    OPERATIONAL = "operational"
    GOVERNANCE = "governance"


@dataclass
class ReadinessCheck:
    """A single readiness criterion."""

    name: str
    category: ReadinessCategory
    description: str
    is_passed: bool
    details: str = ""
    weight: float = 1.0  # Importance weight


@dataclass
class ReadinessReport:
    """Complete readiness assessment report."""

    strategy_name: str
    strategy_version: str
    checks: list[ReadinessCheck] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        """Weighted score (0-100)."""
        if not self.checks:
            return 0.0
        total_weight = sum(c.weight for c in self.checks)
        passed_weight = sum(c.weight for c in self.checks if c.is_passed)
        return (passed_weight / total_weight) * 100.0 if total_weight > 0 else 0.0

    @property
    def is_ready(self) -> bool:
        """True if all critical (weight >= 2.0) checks pass and score >= 80."""
        critical_failed = [c for c in self.checks if c.weight >= 2.0 and not c.is_passed]
        return len(critical_failed) == 0 and self.total_score >= 80.0

    @property
    def failed_checks(self) -> list[ReadinessCheck]:
        return [c for c in self.checks if not c.is_passed]


class ReadinessAssessor:
    """Evaluates strategy readiness for Live trading.

    Runs a comprehensive checklist covering performance, risk,
    stability, operational, and governance criteria.
    """

    def __init__(self, min_paper_days: int = 20) -> None:
        self._min_paper_days = min_paper_days

    def assess(
        self,
        strategy_name: str,
        strategy_version: str,
        # Paper trading metrics
        paper_total_return: float = 0.0,
        paper_max_drawdown: float = 0.0,
        paper_sharpe_ratio: float = 0.0,
        paper_win_rate: float = 0.0,
        paper_total_trades: int = 0,
        paper_days: int = 0,
        # Backtest metrics (for consistency check)
        backtest_total_return: float = 0.0,
        backtest_max_drawdown: float = 0.0,
        backtest_sharpe_ratio: float = 0.0,
        # Risk metrics
        max_daily_loss_pct: float = 0.0,
        max_single_order_pct: float = 0.0,
        # Stability metrics
        param_stability_score: float = 0.0,
        # Governance
        has_approval: bool = False,
        has_version_binding: bool = False,
        has_kill_switch_test: bool = False,
        has_recovery_drill: bool = False,
    ) -> ReadinessReport:
        """Run the full readiness assessment."""
        report = ReadinessReport(
            strategy_name=strategy_name,
            strategy_version=strategy_version,
        )

        # ── Performance checks ──
        report.checks.append(ReadinessCheck(
            name="positive_return",
            category=ReadinessCategory.PERFORMANCE,
            description="Paper trading total return must be positive",
            is_passed=paper_total_return > 0,
            details=f"Return: {paper_total_return:.2f}%",
            weight=2.0,
        ))

        report.checks.append(ReadinessCheck(
            name="sufficient_sharpe",
            category=ReadinessCategory.PERFORMANCE,
            description="Sharpe ratio must exceed 0.5",
            is_passed=paper_sharpe_ratio > 0.5,
            details=f"Sharpe: {paper_sharpe_ratio:.2f}",
            weight=2.0,
        ))

        report.checks.append(ReadinessCheck(
            name="sufficient_trades",
            category=ReadinessCategory.PERFORMANCE,
            description="Must have at least 20 trades in paper trading",
            is_passed=paper_total_trades >= 20,
            details=f"Trades: {paper_total_trades}",
            weight=1.5,
        ))

        report.checks.append(ReadinessCheck(
            name="reasonable_drawdown",
            category=ReadinessCategory.PERFORMANCE,
            description="Max drawdown must be under 15%",
            is_passed=paper_max_drawdown < 15.0,
            details=f"Drawdown: {paper_max_drawdown:.2f}%",
            weight=2.0,
        ))

        report.checks.append(ReadinessCheck(
            name="win_rate_above_threshold",
            category=ReadinessCategory.PERFORMANCE,
            description="Win rate must be above 40%",
            is_passed=paper_win_rate > 40.0,
            details=f"Win rate: {paper_win_rate:.1f}%",
            weight=1.0,
        ))

        # ── Risk checks ──
        report.checks.append(ReadinessCheck(
            name="daily_loss_within_limit",
            category=ReadinessCategory.RISK,
            description="Max daily loss must be under 3%",
            is_passed=max_daily_loss_pct < 3.0,
            details=f"Max daily loss: {max_daily_loss_pct:.2f}%",
            weight=2.0,
        ))

        report.checks.append(ReadinessCheck(
            name="single_order_within_limit",
            category=ReadinessCategory.RISK,
            description="Max single order must be under 10% of capital",
            is_passed=max_single_order_pct < 10.0,
            details=f"Max single order: {max_single_order_pct:.2f}%",
            weight=1.5,
        ))

        # ── Stability checks ──
        report.checks.append(ReadinessCheck(
            name="backtest_paper_consistency",
            category=ReadinessCategory.STABILITY,
            description="Paper performance must be consistent with backtest",
            is_passed=abs(paper_total_return - backtest_total_return) < max(10.0, abs(backtest_total_return) * 0.5),
            details=f"Backtest return: {backtest_total_return:.2f}%, Paper return: {paper_total_return:.2f}%",
            weight=2.0,
        ))

        report.checks.append(ReadinessCheck(
            name="param_stability",
            category=ReadinessCategory.STABILITY,
            description="Parameter stability score must be above 0.7",
            is_passed=param_stability_score > 0.7,
            details=f"Stability score: {param_stability_score:.2f}",
            weight=1.5,
        ))

        report.checks.append(ReadinessCheck(
            name="sufficient_paper_duration",
            category=ReadinessCategory.STABILITY,
            description=f"Must have at least {self._min_paper_days} paper trading days",
            is_passed=paper_days >= self._min_paper_days,
            details=f"Paper days: {paper_days}",
            weight=1.5,
        ))

        # ── Operational checks ──
        report.checks.append(ReadinessCheck(
            name="kill_switch_tested",
            category=ReadinessCategory.OPERATIONAL,
            description="Kill switch must be tested",
            is_passed=has_kill_switch_test,
            details="Kill switch drill completed" if has_kill_switch_test else "NOT TESTED",
            weight=2.0,
        ))

        report.checks.append(ReadinessCheck(
            name="recovery_drill_completed",
            category=ReadinessCategory.OPERATIONAL,
            description="Recovery drill must be completed",
            is_passed=has_recovery_drill,
            details="Recovery drill completed" if has_recovery_drill else "NOT TESTED",
            weight=2.0,
        ))

        # ── Governance checks ──
        report.checks.append(ReadinessCheck(
            name="approval_obtained",
            category=ReadinessCategory.GOVERNANCE,
            description="Human approval must be obtained",
            is_passed=has_approval,
            details="Approved" if has_approval else "NOT APPROVED",
            weight=3.0,
        ))

        report.checks.append(ReadinessCheck(
            name="version_binding_complete",
            category=ReadinessCategory.GOVERNANCE,
            description="Version binding must be complete for traceability",
            is_passed=has_version_binding,
            details="Version binding complete" if has_version_binding else "INCOMPLETE",
            weight=2.0,
        ))

        return report
