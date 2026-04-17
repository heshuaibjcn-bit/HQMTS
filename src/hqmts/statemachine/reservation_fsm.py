"""CashReservation state machine (SAD 7.4).

States: active, partially_consumed, fully_consumed, released, expired, invalid

Constraints:
- Only active or partially_consumed reservations can be consumed
- Agent cannot release reservations (enforced at service layer)
"""

from __future__ import annotations

from hqmts.core.enums import ReservationStatus
from hqmts.statemachine.base import StateMachine

RESERVATION_TRANSITIONS: dict[ReservationStatus, set[ReservationStatus]] = {
    ReservationStatus.ACTIVE: {
        ReservationStatus.PARTIALLY_CONSUMED,
        ReservationStatus.FULLY_CONSUMED,
        ReservationStatus.RELEASED,
        ReservationStatus.EXPIRED,
        ReservationStatus.INVALID,
    },
    ReservationStatus.PARTIALLY_CONSUMED: {
        ReservationStatus.FULLY_CONSUMED,
        ReservationStatus.RELEASED,
        ReservationStatus.EXPIRED,
        ReservationStatus.INVALID,
    },
    ReservationStatus.FULLY_CONSUMED: set(),  # Terminal
    ReservationStatus.RELEASED: set(),  # Terminal
    ReservationStatus.EXPIRED: set(),  # Terminal
    ReservationStatus.INVALID: set(),  # Terminal
}

RESERVATION_TERMINAL_STATES: set[ReservationStatus] = {
    ReservationStatus.FULLY_CONSUMED,
    ReservationStatus.RELEASED,
    ReservationStatus.EXPIRED,
    ReservationStatus.INVALID,
}

reservation_fsm = StateMachine[ReservationStatus](
    entity_type="CashReservation",
    transitions=RESERVATION_TRANSITIONS,
    terminal_states=RESERVATION_TERMINAL_STATES,
)
