"""Rejection handler with taxonomy and remediation (SAD Section 20).

19 rejection types with specific remediation strategies.
"""

from __future__ import annotations

from dataclasses import dataclass

from hqmts.core.enums import RejectReason


@dataclass
class RejectionAction:
    """Result of rejection analysis."""

    reject_reason: RejectReason
    retryable: bool
    max_retries: int
    requires_manual_review: bool
    action_description: str


# Rejection taxonomy and remediation table from SAD 20.2
REJECTION_STRATEGIES: dict[RejectReason, RejectionAction] = {
    RejectReason.NETWORK_ERROR: RejectionAction(
        reject_reason=RejectReason.NETWORK_ERROR,
        retryable=True,
        max_retries=3,
        requires_manual_review=False,
        action_description="Network error — limited retry allowed",
    ),
    RejectReason.ADAPTER_INTERNAL_ERROR: RejectionAction(
        reject_reason=RejectReason.ADAPTER_INTERNAL_ERROR,
        retryable=True,
        max_retries=2,
        requires_manual_review=False,
        action_description="Adapter internal error — limited retry, escalate if exceeded",
    ),
    RejectReason.INVALID_PARAMETER: RejectionAction(
        reject_reason=RejectReason.INVALID_PARAMETER,
        retryable=False,
        max_retries=0,
        requires_manual_review=False,
        action_description="Invalid parameter — immediate fail, no retry",
    ),
    RejectReason.BROKER_REJECT: RejectionAction(
        reject_reason=RejectReason.BROKER_REJECT,
        retryable=False,
        max_retries=0,
        requires_manual_review=True,
        action_description="Broker reject — classify and analyze",
    ),
    RejectReason.EXCHANGE_REJECT: RejectionAction(
        reject_reason=RejectReason.EXCHANGE_REJECT,
        retryable=False,
        max_retries=0,
        requires_manual_review=True,
        action_description="Exchange reject — no retry",
    ),
    RejectReason.MARKET_UNTRADABLE: RejectionAction(
        reject_reason=RejectReason.MARKET_UNTRADABLE,
        retryable=False,
        max_retries=0,
        requires_manual_review=False,
        action_description="Market untradable — delay or reject",
    ),
    RejectReason.PRICE_OUT_OF_LIMIT: RejectionAction(
        reject_reason=RejectReason.PRICE_OUT_OF_LIMIT,
        retryable=True,
        max_retries=1,
        requires_manual_review=False,
        action_description="Price out of limit — recalculate price once or reject",
    ),
    RejectReason.INSUFFICIENT_CASH: RejectionAction(
        reject_reason=RejectReason.INSUFFICIENT_CASH,
        retryable=False,
        max_retries=0,
        requires_manual_review=False,
        action_description="Insufficient cash — release reservation and reject",
    ),
    RejectReason.INSUFFICIENT_POSITION: RejectionAction(
        reject_reason=RejectReason.INSUFFICIENT_POSITION,
        retryable=False,
        max_retries=0,
        requires_manual_review=True,
        action_description="Insufficient position — reject and reconcile",
    ),
    RejectReason.RISK_REJECT: RejectionAction(
        reject_reason=RejectReason.RISK_REJECT,
        retryable=False,
        max_retries=0,
        requires_manual_review=False,
        action_description="Risk reject — no retry",
    ),
    RejectReason.DUPLICATE_SUBMIT: RejectionAction(
        reject_reason=RejectReason.DUPLICATE_SUBMIT,
        retryable=False,
        max_retries=0,
        requires_manual_review=False,
        action_description="Duplicate submit — idempotency interception, query status",
    ),
    RejectReason.UNKNOWN_REJECT: RejectionAction(
        reject_reason=RejectReason.UNKNOWN_REJECT,
        retryable=False,
        max_retries=0,
        requires_manual_review=True,
        action_description="Unknown rejection — escalate to manual review",
    ),
    RejectReason.UNAUTHORIZED_SOURCE: RejectionAction(
        reject_reason=RejectReason.UNAUTHORIZED_SOURCE,
        retryable=False,
        max_retries=0,
        requires_manual_review=True,
        action_description="Unauthorized source — reject and security alert",
    ),
    RejectReason.POLICY_BLOCKED: RejectionAction(
        reject_reason=RejectReason.POLICY_BLOCKED,
        retryable=False,
        max_retries=0,
        requires_manual_review=True,
        action_description="Policy blocked — reject and audit",
    ),
    RejectReason.KILL_SWITCH: RejectionAction(
        reject_reason=RejectReason.KILL_SWITCH,
        retryable=False,
        max_retries=0,
        requires_manual_review=True,
        action_description="Kill switch triggered, all trading halted",
    ),
    RejectReason.SIGNAL_EXPIRED: RejectionAction(
        reject_reason=RejectReason.SIGNAL_EXPIRED,
        retryable=False,
        max_retries=0,
        requires_manual_review=False,
        action_description="Signal has expired, generate new signal",
    ),
    RejectReason.STRATEGY_NOT_LIVE: RejectionAction(
        reject_reason=RejectReason.STRATEGY_NOT_LIVE,
        retryable=False,
        max_retries=0,
        requires_manual_review=True,
        action_description="Strategy not in live_running state",
    ),
    RejectReason.MARKET_CLOSED: RejectionAction(
        reject_reason=RejectReason.MARKET_CLOSED,
        retryable=True,
        max_retries=3,
        requires_manual_review=False,
        action_description="Market is closed, retry during trading hours",
    ),
    RejectReason.ORDER_FREQUENCY_EXCEEDED: RejectionAction(
        reject_reason=RejectReason.ORDER_FREQUENCY_EXCEEDED,
        retryable=True,
        max_retries=1,
        requires_manual_review=False,
        action_description="Order frequency limit exceeded, slow down",
    ),
}


class RejectHandler:
    """Handles order rejection with remediation strategies."""

    def classify(self, raw_reason: str) -> RejectReason:
        """Classify a raw rejection reason into the taxonomy."""
        reason_lower = raw_reason.lower()

        classification_map = {
            "network": RejectReason.NETWORK_ERROR,
            "timeout": RejectReason.NETWORK_ERROR,
            "connection": RejectReason.NETWORK_ERROR,
            "adapter": RejectReason.ADAPTER_INTERNAL_ERROR,
            "internal": RejectReason.ADAPTER_INTERNAL_ERROR,
            "invalid": RejectReason.INVALID_PARAMETER,
            "parameter": RejectReason.INVALID_PARAMETER,
            "broker": RejectReason.BROKER_REJECT,
            "exchange": RejectReason.EXCHANGE_REJECT,
            "untradable": RejectReason.MARKET_UNTRADABLE,
            "suspended": RejectReason.MARKET_UNTRADABLE,
            "rate limit": RejectReason.ORDER_FREQUENCY_EXCEEDED,
            "frequency": RejectReason.ORDER_FREQUENCY_EXCEEDED,
            "limit": RejectReason.PRICE_OUT_OF_LIMIT,
            "cash": RejectReason.INSUFFICIENT_CASH,
            "fund": RejectReason.INSUFFICIENT_CASH,
            "position": RejectReason.INSUFFICIENT_POSITION,
            "holding": RejectReason.INSUFFICIENT_POSITION,
            "risk": RejectReason.RISK_REJECT,
            "duplicate": RejectReason.DUPLICATE_SUBMIT,
            "unauthorized": RejectReason.UNAUTHORIZED_SOURCE,
            "policy": RejectReason.POLICY_BLOCKED,
            "kill_switch": RejectReason.KILL_SWITCH,
            "kill switch": RejectReason.KILL_SWITCH,
            "signal expired": RejectReason.SIGNAL_EXPIRED,
            "signal_expired": RejectReason.SIGNAL_EXPIRED,
            "not live": RejectReason.STRATEGY_NOT_LIVE,
            "not_live": RejectReason.STRATEGY_NOT_LIVE,
            "market closed": RejectReason.MARKET_CLOSED,
            "market_closed": RejectReason.MARKET_CLOSED,
            "trading hours": RejectReason.MARKET_CLOSED,
        }

        for keyword, reason in classification_map.items():
            if keyword in reason_lower:
                return reason

        return RejectReason.UNKNOWN_REJECT

    def get_remediation(self, reason: RejectReason) -> RejectionAction:
        """Get the remediation strategy for a rejection reason."""
        return REJECTION_STRATEGIES.get(reason, REJECTION_STRATEGIES[RejectReason.UNKNOWN_REJECT])

    def should_retry(self, reason: RejectReason, attempt: int) -> bool:
        """Check if the rejection allows a retry at the given attempt count."""
        strategy = self.get_remediation(reason)
        return strategy.retryable and attempt < strategy.max_retries
