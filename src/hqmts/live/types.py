"""Live startup types (SAD 22.1)."""

from __future__ import annotations

from dataclasses import dataclass, field

from hqmts.core.enums import StartupStepStatus
from hqmts.core.types import now_shanghai


@dataclass
class StepResult:
    """Result of a single startup step."""

    step_number: int
    name: str
    status: StartupStepStatus
    duration_ms: float = 0.0
    detail: str = ""


@dataclass
class SystemReadiness:
    """Current system readiness status."""

    is_ready: bool = False
    current_step: int = 0
    total_steps: int = 14
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    started_at: str = ""
    health_summary: dict = field(default_factory=dict)


@dataclass
class StartupResult:
    """Result of the full startup sequence."""

    success: bool
    steps: list[StepResult] = field(default_factory=list)
    readiness: SystemReadiness = field(default_factory=SystemReadiness)
    total_duration_ms: float = 0.0
