"""Tests for the rejection handler."""

import pytest

from hqmts.core.enums import RejectReason
from hqmts.execution.reject_handler import RejectHandler


@pytest.fixture
def handler():
    return RejectHandler()


class TestRejectHandler:
    def test_classify_network_error(self, handler):
        assert handler.classify("Network connection timeout") == RejectReason.NETWORK_ERROR

    def test_classify_invalid_parameter(self, handler):
        assert handler.classify("Invalid order parameter") == RejectReason.INVALID_PARAMETER

    def test_classify_insufficient_cash(self, handler):
        assert handler.classify("Insufficient cash balance") == RejectReason.INSUFFICIENT_CASH

    def test_classify_insufficient_position(self, handler):
        assert handler.classify("Insufficient position to sell") == RejectReason.INSUFFICIENT_POSITION

    def test_classify_risk_reject(self, handler):
        assert handler.classify("Risk check rejected") == RejectReason.RISK_REJECT

    def test_classify_duplicate(self, handler):
        assert handler.classify("Duplicate order submission") == RejectReason.DUPLICATE_SUBMIT

    def test_classify_unknown(self, handler):
        assert handler.classify("Something completely unexpected") == RejectReason.UNKNOWN_REJECT

    def test_remediation_network_retryable(self, handler):
        action = handler.get_remediation(RejectReason.NETWORK_ERROR)
        assert action.retryable is True
        assert action.max_retries == 3

    def test_remediation_invalid_param_not_retryable(self, handler):
        action = handler.get_remediation(RejectReason.INVALID_PARAMETER)
        assert action.retryable is False

    def test_remediation_price_retry_once(self, handler):
        action = handler.get_remediation(RejectReason.PRICE_OUT_OF_LIMIT)
        assert action.retryable is True
        assert action.max_retries == 1

    def test_should_retry_within_limit(self, handler):
        assert handler.should_retry(RejectReason.NETWORK_ERROR, 0) is True
        assert handler.should_retry(RejectReason.NETWORK_ERROR, 2) is True
        assert handler.should_retry(RejectReason.NETWORK_ERROR, 3) is False

    def test_should_not_retry_non_retryable(self, handler):
        assert handler.should_retry(RejectReason.INVALID_PARAMETER, 0) is False
        assert handler.should_retry(RejectReason.RISK_REJECT, 0) is False
