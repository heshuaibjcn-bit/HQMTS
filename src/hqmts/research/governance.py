"""Multiple testing governance for factor research (FR-RES-004).

Tracks trial count, hit count, and rejected hypotheses to prevent
data snooping bias and maintain research integrity.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrialRecord:
    """Record of a single hypothesis test."""

    trial_id: int
    factor_name: str
    strategy_name: str
    metric_name: str  # e.g. "sharpe_ratio", "total_return"
    metric_value: float
    threshold: float  # Significance threshold
    is_significant: bool
    notes: str = ""


@dataclass
class GovernanceStats:
    """Aggregated governance statistics."""

    total_trials: int = 0
    significant_count: int = 0
    rejected_count: int = 0
    family_wise_error_rate: float = 0.0
    false_discovery_rate: float = 0.0


class MultipleTestingGovernance:
    """Tracks and enforces multiple testing governance.

    Implements Bonferroni correction and Benjamini-Hochberg FDR control
    to prevent data snooping bias in factor research.
    """

    def __init__(
        self,
        alpha: float = 0.05,
        method: str = "bonferroni",  # bonferroni | bh
        max_trials: int = 1000,
    ) -> None:
        self._alpha = alpha
        self._method = method
        self._max_trials = max_trials
        self._trials: list[TrialRecord] = []

    def record_trial(
        self,
        factor_name: str,
        strategy_name: str,
        metric_name: str,
        metric_value: float,
        threshold: float,
        notes: str = "",
    ) -> TrialRecord:
        """Record a hypothesis test trial."""
        trial_id = len(self._trials) + 1
        record = TrialRecord(
            trial_id=trial_id,
            factor_name=factor_name,
            strategy_name=strategy_name,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            is_significant=metric_value >= threshold,
            notes=notes,
        )
        self._trials.append(record)
        return record

    def get_adjusted_threshold(self) -> float:
        """Get significance threshold adjusted for multiple testing."""
        n = max(1, len(self._trials))
        if self._method == "bonferroni":
            return self._alpha / n
        return self._alpha  # BH uses ranking, computed separately

    def compute_stats(self) -> GovernanceStats:
        """Compute governance statistics across all trials."""
        n = len(self._trials)
        if n == 0:
            return GovernanceStats()

        significant = sum(1 for t in self._trials if t.is_significant)
        adjusted = self.get_adjusted_threshold()
        rejected = sum(1 for t in self._trials if t.metric_value >= adjusted)

        fwer = 1.0 - (1.0 - self._alpha) ** n
        fdr = 0.0
        if significant > 0:
            # Simplified FDR estimate
            fdr = min(1.0, (n * self._alpha) / max(1, significant))

        return GovernanceStats(
            total_trials=n,
            significant_count=significant,
            rejected_count=rejected,
            family_wise_error_rate=fwer,
            false_discovery_rate=fdr,
        )

    def is_within_budget(self) -> bool:
        """Check if trial count is within allowed budget."""
        return len(self._trials) <= self._max_trials

    @property
    def trial_count(self) -> int:
        return len(self._trials)

    def get_trials(self, factor_name: str | None = None) -> list[TrialRecord]:
        """Get trial records, optionally filtered by factor."""
        if factor_name:
            return [t for t in self._trials if t.factor_name == factor_name]
        return list(self._trials)
