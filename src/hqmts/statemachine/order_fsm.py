"""Order state machine (SAD 15.1).

States: pending, submitted, accepted, partial_filled, filled,
        canceled, rejected, error, suspended, expired

Terminal states: filled, canceled, rejected, expired
"""

from __future__ import annotations

from hqmts.core.enums import OrderStatus
from hqmts.statemachine.base import StateMachine

# Transition table from SAD 15.1
ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.SUBMITTED, OrderStatus.CANCELED},
    OrderStatus.SUBMITTED: {
        OrderStatus.ACCEPTED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELED,
    },
    OrderStatus.ACCEPTED: {
        OrderStatus.PARTIAL_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
    },
    OrderStatus.PARTIAL_FILLED: {
        OrderStatus.PARTIAL_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
    },
    OrderStatus.FILLED: set(),  # Terminal
    OrderStatus.CANCELED: set(),  # Terminal
    OrderStatus.REJECTED: set(),  # Terminal
    OrderStatus.ERROR: {
        OrderStatus.ACCEPTED,
        OrderStatus.PARTIAL_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.SUSPENDED: {
        OrderStatus.ACCEPTED,
        OrderStatus.CANCELED,
    },
    OrderStatus.EXPIRED: set(),  # Terminal
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
