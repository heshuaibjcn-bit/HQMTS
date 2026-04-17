"""Notification channels for alert delivery (SAD 28).

Provides a pluggable interface for sending alerts to different
destinations: log, webhook, email (stub).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

from hqmts.monitoring.alerts import Alert

logger = logging.getLogger(__name__)


class NotificationChannel(Protocol):
    """Interface for sending alert notifications."""

    def send(self, alert: Alert) -> bool:
        """Send an alert notification. Returns True if successful."""
        ...


@dataclass
class LogChannel:
    """Send alerts to Python logging."""

    level: int = logging.WARNING

    def send(self, alert: Alert) -> bool:
        logger.log(
            self.level,
            "ALERT [%s] %s: %s (metric=%s value=%s)",
            alert.level.value,
            alert.rule_name,
            alert.message,
            alert.metric,
            alert.value,
        )
        return True


@dataclass
class WebhookChannel:
    """Send alerts to an HTTP webhook."""

    url: str
    timeout_seconds: float = 5.0

    def send(self, alert: Alert) -> bool:
        """Post alert as JSON to the configured webhook URL."""
        try:
            import urllib.request

            payload = json.dumps({
                "alert_id": alert.alert_id,
                "rule_name": alert.rule_name,
                "level": alert.level.value,
                "metric": alert.metric,
                "value": alert.value,
                "threshold": alert.threshold,
                "message": alert.message,
                "detected_at": alert.detected_at.isoformat(),
                "routing_target": alert.routing_target,
            }).encode("utf-8")

            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                return resp.status == 200
        except Exception:
            logger.exception("Failed to send alert %s to webhook %s", alert.alert_id, self.url)
            return False


@dataclass
class InMemoryChannel:
    """Collect alerts in memory for testing."""

    alerts: list[Alert] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.alerts is None:
            self.alerts = []

    def send(self, alert: Alert) -> bool:
        self.alerts.append(alert)
        return True

    def clear(self) -> None:
        self.alerts.clear()


class NotificationRouter:
    """Routes alerts to appropriate notification channels based on level."""

    def __init__(self) -> None:
        self._channels: dict[str, list[NotificationChannel]] = {
            "immediate_halt": [LogChannel(logging.CRITICAL)],
            "human_intervention": [LogChannel(logging.ERROR)],
            "intraday_watch": [LogChannel(logging.WARNING)],
            "info_log": [LogChannel(logging.INFO)],
        }

    def add_channel(self, routing_target: str, channel: NotificationChannel) -> None:
        """Add a notification channel for a routing target."""
        self._channels.setdefault(routing_target, []).append(channel)

    def route(self, alert: Alert) -> list[bool]:
        """Send alert to all channels matching its routing target."""
        channels = self._channels.get(alert.routing_target, [])
        return [ch.send(alert) for ch in channels]
