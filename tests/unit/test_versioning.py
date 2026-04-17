"""Tests for data versioning service (FR-DATA-006)."""

from __future__ import annotations

from hqmts.data.versioning import VersionBindingService, VersionBinding, ENGINE_VERSION


class TestVersionBindingService:
    def test_create_binding_basic(self):
        svc = VersionBindingService()
        binding = svc.create_binding("backtest_result", "bt-001")
        assert binding.entity_type == "backtest_result"
        assert binding.entity_id == "bt-001"
        assert binding.engine_version == ENGINE_VERSION
        assert binding.version_binding_id  # non-empty

    def test_create_binding_with_versions(self):
        svc = VersionBindingService()
        binding = svc.create_binding(
            "backtest_result",
            "bt-002",
            versions={
                "data_version": "v1",
                "strategy_version": "v2",
                "param_version": "v3",
                "risk_rule_version": "v1.1",
            },
        )
        assert binding.data_version == "v1"
        assert binding.strategy_version == "v2"
        assert binding.param_version == "v3"
        assert binding.risk_rule_version == "v1.1"

    def test_get_binding(self):
        svc = VersionBindingService()
        svc.create_binding("signal", "sig-001", versions={"strategy_version": "v1"})
        binding = svc.get_binding("signal", "sig-001")
        assert binding is not None
        assert binding.strategy_version == "v1"

    def test_get_binding_not_found(self):
        svc = VersionBindingService()
        assert svc.get_binding("signal", "nonexistent") is None

    def test_get_for_signal(self):
        svc = VersionBindingService()
        svc.create_binding("signal", "sig-002")
        assert svc.get_for_signal("sig-002") is not None
        assert svc.get_for_signal("nonexistent") is None

    def test_get_for_backtest(self):
        svc = VersionBindingService()
        svc.create_binding("backtest_result", "bt-010")
        assert svc.get_for_backtest("bt-010") is not None

    def test_binding_is_immutable(self):
        svc = VersionBindingService()
        binding = svc.create_binding("order", "ord-001")
        assert isinstance(binding, VersionBinding)
        # Frozen dataclass
        try:
            binding.entity_type = "modified"  # type: ignore
            assert False, "Should have raised"
        except AttributeError:
            pass

    def test_clear_store(self):
        svc = VersionBindingService()
        svc.create_binding("backtest_result", "bt-100")
        assert svc.get_for_backtest("bt-100") is not None
        svc.clear()
        assert svc.get_for_backtest("bt-100") is None

    def test_all_version_fields_set(self):
        svc = VersionBindingService()
        all_versions = {f"{k}_version": f"v_{k}" for k in [
            "data", "feature", "strategy", "param", "risk_rule",
            "execution_policy", "engine", "qmt_adapter", "agent_workflow",
            "tool", "prompt", "live_config",
        ]}
        binding = svc.create_binding("signal", "sig-full", versions=all_versions)
        assert binding.data_version == "v_data"
        assert binding.feature_version == "v_feature"
        assert binding.strategy_version == "v_strategy"
        assert binding.param_version == "v_param"
        assert binding.risk_rule_version == "v_risk_rule"
        assert binding.execution_policy_version == "v_execution_policy"
        assert binding.engine_version == "v_engine"
        assert binding.qmt_adapter_version == "v_qmt_adapter"
        assert binding.agent_workflow_version == "v_agent_workflow"
        assert binding.tool_version == "v_tool"
        assert binding.prompt_version == "v_prompt"
        assert binding.live_config_version == "v_live_config"

    def test_isolated_stores(self):
        """Each service instance can have its own store."""
        store_a: dict = {}
        store_b: dict = {}
        svc_a = VersionBindingService(store=store_a)
        svc_b = VersionBindingService(store=store_b)
        svc_a.create_binding("signal", "sig-a")
        assert svc_b.get_binding("signal", "sig-a") is None
        assert svc_a.get_binding("signal", "sig-a") is not None
