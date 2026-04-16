"""Order state machine (SAD 15.1).

States: created, submitting, submitted, accepted, partially_filled, filled,
        cancel_pending, canceled, rejected, expired, uncertain

Terminal states: filled, canceled, rejected, expired
"""

from __future__ import annotations

from hqmts.core.enums import OrderStatus
from hqmts.statemachine.base import StateMachine

# Transition table from SAD 15.1
ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.SUBMITTING, OrderStatus.REJECTED, OrderStatus.EXPIRED},
    OrderStatus.SUBMITTING: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.UNCERTAIN},
    OrderStatus.SUBMITTED: {
        OrderStatus.ACCEPTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.REJECTED,
        OrderStatus.UNCERTAIN,
    },
    OrderStatus.ACCEPTED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.UNCERTAIN,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.CANCELED,
        OrderStatus.UNCERTAIN,
    },
    OrderStatus.FILLED: set(),  # Terminal
    OrderStatus.CANCEL_PENDING: {
        OrderStatus.CANCELED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.UNCERTAIN,
    },
    OrderStatus.CANCELED: set(),  # Terminal
    OrderStatus.REJECTED: set(),  # Terminal
    OrderStatus.EXPIRED: set(),  # Terminal
    OrderStatus.UNCERTAIN: {
        OrderStatus.ACCEPTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    },
}

ORDER_TERMINAL_STATES: set[OrderStatus] = {
    OrderStatus.FILLED,
    OrderStatus.CANCELED,
    OrderStatus.REJECTED,
    OrderStatus.EXPIRED,
}

order_fsm = StateMachine[OrderStatus](
    entity_type="Order",
    transitions=ORDER_TRANSITIONS,
    terminal_states=ORDER_TERMINAL_STATES,
)
