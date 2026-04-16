"""Reconciliation service (SAD Sections 15.4, 22).

Compares local state vs QMT broker state for orders, trades, positions, accounts.
Detects external manual events and escalates mismatches.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from hqmts.core.enums import ReconciliationStatus
from hqmts.core.types import ReconciliationId


class ReconcileScope(str, Enum):
    ORDER = "order"
    TRADE = "trade"
    POSITION = "position"
    ACCOUNT = "account"


@dataclass
class ReconcileDiff:
    """A single difference found during reconciliation."""

    field_name: str
    local_value: str
    broker_value: str
    severity: str = "warning"  # info, warning, critical


@dataclass
class ReconcileResult:
    """Result of a reconciliation session."""

    reconciliation_id: str
    scope_type: str
    scope_id: str
    status: ReconciliationStatus
    diffs: list[ReconcileDiff] = field(default_factory=list)
    external_events_detected: int = 0

    @property
    def has_mismatch(self) -> bool:
        return len(self.diffs) > 0

    @property
    def has_critical(self) -> bool:
        return any(d.severity == "critical" for d in self.diffs)


class ReconciliationService:
    """Orchestrates reconciliation between local state and QMT.

    Agent can analyze mismatches and generate correction proposals,
    but cannot directly execute corrections.
    """

    async def reconcile_orders(
        self,
        account_id: str,
        local_orders: list[dict],
        broker_orders: list[dict],
    ) -> ReconcileResult:
        """Compare local orders against broker orders."""
        diffs: list[ReconcileDiff] = []
        broker_map = {o.get("broker_order_id"): o for o in broker_orders}

        for local in local_orders:
            broker_id = local.get("broker_order_id")
            if not broker_id:
                continue

            broker = broker_map.get(broker_id)
            if broker is None:
                diffs.append(ReconcileDiff(
                    field_name="existence",
                    local_value=f"order_id={local.get('order_id')}",
                    broker_value="NOT_FOUND",
                    severity="critical",
                ))
                continue

            # Compare status
            if local.get("status") != broker.get("status"):
                diffs.append(ReconcileDiff(
                    field_name="status",
                    local_value=str(local.get("status")),
                    broker_value=str(broker.get("status")),
                    severity="warning",
                ))

            # Compare filled quantity
            if local.get("filled_quantity") != broker.get("filled_quantity"):
                diffs.append(ReconcileDiff(
                    field_name="filled_quantity",
                    local_value=str(local.get("filled_quantity")),
                    broker_value=str(broker.get("filled_quantity")),
                    severity="critical",
                ))

        # Check for broker orders not in local
        local_broker_ids = {o.get("broker_order_id") for o in local_orders}
        external_count = 0
        for broker in broker_orders:
            if broker.get("broker_order_id") not in local_broker_ids:
                external_count += 1
                diffs.append(ReconcileDiff(
                    field_name="external_order",
                    local_value="NOT_FOUND",
                    broker_value=f"broker_order_id={broker.get('broker_order_id')}",
                    severity="critical",
                ))

        status = (
            ReconciliationStatus.MATCHED
            if not diffs
            else ReconciliationStatus.MISMATCH_DETECTED
        )

        return ReconcileResult(
            reconciliation_id=str(uuid.uuid4()),
            scope_type=ReconcileScope.ORDER.value,
            scope_id=account_id,
            status=status,
            diffs=diffs,
            external_events_detected=external_count,
        )

    async def reconcile_positions(
        self,
        account_id: str,
        local_positions: list[dict],
        broker_positions: list[dict],
    ) -> ReconcileResult:
        """Compare local positions against broker positions."""
        diffs: list[ReconcileDiff] = []
        broker_map = {p.get("instrument_id"): p for p in broker_positions}

        for local in local_positions:
            instrument_id = local.get("instrument_id")
            broker = broker_map.get(instrument_id)

            if broker is None:
                diffs.append(ReconcileDiff(
                    field_name="position_existence",
                    local_value=f"instrument={instrument_id}, qty={local.get('total_quantity')}",
                    broker_value="NOT_FOUND",
                    severity="critical",
                ))
                continue

            if local.get("total_quantity") != broker.get("total_quantity"):
                diffs.append(ReconcileDiff(
                    field_name="total_quantity",
                    local_value=str(local.get("total_quantity")),
                    broker_value=str(broker.get("total_quantity")),
                    severity="critical",
                ))

            if local.get("available_quantity") != broker.get("available_quantity"):
                diffs.append(ReconcileDiff(
                    field_name="available_quantity",
                    local_value=str(local.get("available_quantity")),
                    broker_value=str(broker.get("available_quantity")),
                    severity="warning",
                ))

        return ReconcileResult(
            reconciliation_id=str(uuid.uuid4()),
            scope_type=ReconcileScope.POSITION.value,
            scope_id=account_id,
            status=ReconciliationStatus.MATCHED if not diffs else ReconciliationStatus.MISMATCH_DETECTED,
            diffs=diffs,
        )

    async def reconcile_account(
        self,
        account_id: str,
        local_account: dict,
        broker_account: dict,
    ) -> ReconcileResult:
        """Compare local account state against broker account."""
        diffs: list[ReconcileDiff] = []

        for field_name in ["total_asset", "available_cash", "market_value"]:
            local_val = Decimal(str(local_account.get(field_name, 0)))
            broker_val = Decimal(str(broker_account.get(field_name, 0)))
            if local_val != broker_val:
                diffs.append(ReconcileDiff(
                    field_name=field_name,
                    local_value=str(local_val),
                    broker_value=str(broker_val),
                    severity="critical" if field_name == "available_cash" else "warning",
                ))

        return ReconcileResult(
            reconciliation_id=str(uuid.uuid4()),
            scope_type=ReconcileScope.ACCOUNT.value,
            scope_id=account_id,
            status=ReconciliationStatus.MATCHED if not diffs else ReconciliationStatus.MISMATCH_DETECTED,
            diffs=diffs,
        )

    async def reconcile_trades(
        self,
        account_id: str,
        local_trades: list[dict],
        broker_trades: list[dict],
    ) -> ReconcileResult:
        """Compare local trades against broker trades."""
        diffs: list[ReconcileDiff] = []
        broker_map = {t.get("broker_trade_id"): t for t in broker_trades}

        for local in local_trades:
            broker_trade_id = local.get("broker_trade_id")
            if not broker_trade_id:
                continue

            broker = broker_map.get(broker_trade_id)
            if broker is None:
                diffs.append(ReconcileDiff(
                    field_name="trade_existence",
                    local_value=f"trade_id={local.get('trade_id')}",
                    broker_value="NOT_FOUND",
                    severity="critical",
                ))
                continue

            # Compare fill quantity
            if local.get("quantity") != broker.get("quantity"):
                diffs.append(ReconcileDiff(
                    field_name="quantity",
                    local_value=str(local.get("quantity")),
                    broker_value=str(broker.get("quantity")),
                    severity="critical",
                ))

            # Compare fill price
            if local.get("price") != broker.get("price"):
                diffs.append(ReconcileDiff(
                    field_name="price",
                    local_value=str(local.get("price")),
                    broker_value=str(broker.get("price")),
                    severity="critical",
                ))

        # Check for broker trades not in local (external trades)
        local_broker_ids = {t.get("broker_trade_id") for t in local_trades}
        external_count = 0
        for broker in broker_trades:
            if broker.get("broker_trade_id") not in local_broker_ids:
                external_count += 1
                diffs.append(ReconcileDiff(
                    field_name="external_trade",
                    local_value="NOT_FOUND",
                    broker_value=f"broker_trade_id={broker.get('broker_trade_id')}",
                    severity="critical",
                ))

        status = (
            ReconciliationStatus.MATCHED
            if not diffs
            else ReconciliationStatus.MISMATCH_DETECTED
        )

        return ReconcileResult(
            reconciliation_id=str(uuid.uuid4()),
            scope_type=ReconcileScope.TRADE.value,
            scope_id=account_id,
            status=status,
            diffs=diffs,
            external_events_detected=external_count,
        )
