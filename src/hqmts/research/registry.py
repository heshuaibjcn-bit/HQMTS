"""Factor registry with version management (FR-RES-002).

Central registry for all factors. Tracks versions, categories,
and provides lookup by name or category.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hqmts.research.factor import Factor, FactorCategory


@dataclass
class FactorRegistration:
    """Record of a registered factor."""

    factor: Factor
    registered_at: str = ""
    registered_by: str = ""


class FactorRegistry:
    """Central registry for factor discovery and version management."""

    def __init__(self) -> None:
        self._factors: dict[str, FactorRegistration] = {}

    def register(self, factor: Factor, registered_by: str = "system") -> None:
        """Register a factor. Overwrites if same name exists with different version."""
        key = factor.name
        self._factors[key] = FactorRegistration(
            factor=factor,
            registered_by=registered_by,
        )

    def get(self, name: str) -> Factor | None:
        """Get a factor by name."""
        reg = self._factors.get(name)
        return reg.factor if reg else None

    def list_factors(self, category: FactorCategory | None = None) -> list[Factor]:
        """List all registered factors, optionally filtered by category."""
        factors = [r.factor for r in self._factors.values()]
        if category:
            factors = [f for f in factors if f.category == category]
        return factors

    def list_names(self) -> list[str]:
        """List all registered factor names."""
        return list(self._factors.keys())

    def unregister(self, name: str) -> bool:
        """Remove a factor from the registry."""
        if name in self._factors:
            del self._factors[name]
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._factors)


def create_default_registry() -> FactorRegistry:
    """Create a registry pre-loaded with built-in factors."""
    from hqmts.research.factor import (
        ATRFactor,
        BollingerPositionFactor,
        EMAFactor,
        RSIFactor,
        SMAFactor,
        VolumeRatioFactor,
    )

    registry = FactorRegistry()
    for period in [5, 10, 20, 60]:
        registry.register(SMAFactor(period))
        registry.register(EMAFactor(period))
    registry.register(RSIFactor(14))
    registry.register(ATRFactor(14))
    registry.register(VolumeRatioFactor(20))
    registry.register(BollingerPositionFactor(20, 2.0))
    return registry
