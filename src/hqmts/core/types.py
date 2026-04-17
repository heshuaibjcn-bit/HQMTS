"""Shared type definitions — typed IDs and common type aliases."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import NewType

# ── Typed IDs ────────────────────────────────────────────────────────────────
# Using NewType for type-safe ID passing. Prevents accidentally passing
# an OrderId where a SignalId is expected.

InstrumentId = NewType("InstrumentId", str)
AccountId = NewType("AccountId", str)
StrategyId = NewType("StrategyId", str)
StrategyInstanceId = NewType("StrategyInstanceId", str)
SignalId = NewType("SignalId", str)
OrderId = NewType("OrderId", str)
OrderRequestId = NewType("OrderRequestId", str)
TradeId = NewType("TradeId", str)
BrokerOrderId = NewType("BrokerOrderId", str)
BrokerTradeId = NewType("BrokerTradeId", str)
RiskCheckId = NewType("RiskCheckId", str)
ReservationId = NewType("ReservationId", str)
ExecutionIntentId = NewType("ExecutionIntentId", str)
ReconciliationId = NewType("ReconciliationId", str)
RecoveryId = NewType("RecoveryId", str)
DecisionSnapshotId = NewType("DecisionSnapshotId", str)
FeatureSnapshotId = NewType("FeatureSnapshotId", str)
VersionBindingId = NewType("VersionBindingId", str)
AuditEventId = NewType("AuditEventId", str)
ExternalEventId = NewType("ExternalEventId", str)
ActionId = NewType("ActionId", str)
IdempotencyKey = NewType("IdempotencyKey", str)

# Agent governance IDs
AgentTaskId = NewType("AgentTaskId", str)
ProposalId = NewType("ProposalId", str)
ToolInvocationId = NewType("ToolInvocationId", str)
ApprovalRequestId = NewType("ApprovalRequestId", str)
ControlledExecutionId = NewType("ControlledExecutionId", str)
PolicyCheckId = NewType("PolicyCheckId", str)
CorrelationId = NewType("CorrelationId", str)

# Next development phase IDs
CorrectionEventId = NewType("CorrectionEventId", str)
AdmissionId = NewType("AdmissionId", str)

# ── Type Aliases ─────────────────────────────────────────────────────────────

Price = Decimal
Quantity = int
Amount = Decimal
Percentage = Decimal
VersionStr = str

# ── Utility ──────────────────────────────────────────────────────────────────


def now_shanghai() -> datetime:
    """Return current time in Asia/Shanghai timezone (tz-aware)."""
    from dateutil import tz

    return datetime.now(tz.gettz("Asia/Shanghai"))
