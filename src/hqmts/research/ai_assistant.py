"""Factor research AI assistant -- per-stage AI interaction.

Provides structured prompts and response parsing for each of the
6 research workflow stages.
"""

from __future__ import annotations

from typing import Any


class FactorResearchAI:
    """AI assistant that provides stage-aware support for factor research."""

    # Stage-specific structured output tags
    STAGE_TAGS = {
        "exploration": "[SCOPE_SUGGESTION]",
        "hypothesis": "[HYPOTHESIS]",
        "design": "[TRIAL_DESIGN]",
        "execution": "[RISK_WARNING]",
        "validation": "[VALIDATION_VERDICT]",
        "report": "[REPORT_SECTION]",
    }

    @staticmethod
    def build_exploration_prompt(
        research_question: str,
        instruments: list[str] | None = None,
        factor_categories: list[str] | None = None,
    ) -> str:
        """Build prompt for Stage 1: Exploration.

        AI analyzes data availability, recommends factor categories,
        and identifies potential instruments.
        """
        parts = [
            "你是一个因子研究探索助手。用户提出了以下研究问题：",
            f"\n「{research_question}」\n",
            "\n请分析并给出建议：",
            "1. 推荐的因子类别（趋势/动量/波动率/成交量/结构/市场状态/跨周期）",
            "2. 推荐的标的范围",
            "3. 建议的时间范围和数据周期",
            "4. 潜在的数据质量问题或限制",
            "5. 初步的研究方向建议\n",
            "\n使用 [SCOPE_SUGGESTION] 标签包裹你的结构化建议。",
        ]
        if instruments:
            parts.append(f"\n用户已选择标的: {', '.join(instruments)}")
        if factor_categories:
            parts.append(f"\n用户已指定因子类别: {', '.join(factor_categories)}")
        return "\n".join(parts)

    @staticmethod
    def build_hypothesis_prompt(
        research_question: str,
        factor_names: list[str],
        instruments: list[str],
        market_regime: str | None = None,
    ) -> str:
        """Build prompt for Stage 2: Hypothesis generation.

        AI proposes multiple competing hypotheses, identifies confounders.
        """
        parts = [
            "你是一个因子研究假设生成器。基于以下研究问题：",
            f"\n「{research_question}」\n",
            f"\n因子: {', '.join(factor_names)}",
            f"\n标的: {', '.join(instruments)}",
            "\n请生成 3-5 个竞争性假设，每个假设包含：",
            "- prediction: 预测内容（一句话）",
            "- factor_names: 涉及的因子",
            "- expected_effect: 预期效应方向 (positive/negative/non-zero)",
            "- expected_magnitude: 预期效应量（如0.5表示Sharpe提升0.5）",
            "- rationale: 推荐理由",
            "- confidence: 置信度 0.0-1.0",
            "- potential_confounders: 可能的混杂变量",
            "\n使用 [HYPOTHESIS] 标签包裹每个假设。",
        ]
        if market_regime:
            parts.append(f"\n当前市场状态: {market_regime}")
        return "\n".join(parts)

    @staticmethod
    def build_design_prompt(
        hypothesis_prediction: str,
        factor_names: list[str],
        instruments: list[str],
        time_range: str,
        existing_trial_count: int = 0,
    ) -> str:
        """Build prompt for Stage 3: Trial design.

        AI suggests statistical tests, sample sizes, and warns about
        multiple testing impact.
        """
        return (
            "你是一个试验设计专家。请为以下假设设计试验计划：\n"
            f"\n假设: {hypothesis_prediction}"
            f"\n因子: {', '.join(factor_names)}"
            f"\n标的: {', '.join(instruments)}"
            f"\n时间范围: {time_range}"
            f"\n项目中已有试验数: {existing_trial_count}"
            "\n\n请提供："
            "\n1. 训练期/测试期分割建议（防止前视偏差）"
            "\n2. 建议的评估指标和阈值"
            "\n3. 多重检验校正后的 alpha 值"
            "\n4. 所需最小样本量"
            "\n5. 潜在的统计陷阱"
            "\n\n使用 [TRIAL_DESIGN] 标签包裹你的建议。"
        )

    @staticmethod
    def build_execution_monitor_prompt(
        trial_plan: dict[str, Any],
        metrics: dict[str, float] | None = None,
    ) -> str:
        """Build prompt for Stage 4: Execution monitoring."""
        parts = [
            "你是试验执行监控器。当前正在执行以下试验：\n",
            f"因子组合: {', '.join(trial_plan.get('factor_combination', []))}",
            f"\n标的: {', '.join(trial_plan.get('instruments', []))}",
            f"\n训练期: {trial_plan.get('train_period_start', '')} ~ {trial_plan.get('train_period_end', '')}",
            f"\n测试期: {trial_plan.get('test_period_start', '')} ~ {trial_plan.get('test_period_end', '')}",
            f"\n评估指标: {trial_plan.get('metric_name', 'sharpe_ratio')}",
        ]
        if metrics:
            parts.append(f"\n\n当前指标: {metrics}")
            parts.append("\n请检查数据质量并标记任何异常。")
        parts.append("\n\n使用 [RISK_WARNING] 标签标记任何风险或异常。")
        return "\n".join(parts)

    @staticmethod
    def build_validation_prompt(
        hypothesis_prediction: str,
        trial_results: list[dict[str, Any]],
        adjusted_alpha: float,
        total_trials_in_project: int,
    ) -> str:
        """Build prompt for Stage 5: Validation.

        AI challenges significant results, checks out-of-sample stability.
        """
        results_summary = "\n".join(
            f"- 试验{i+1}: metric={r.get('metric_value', 'N/A')}, "
            f"显著={'是' if r.get('is_significant') else '否'}, "
            f"训练={r.get('train_metric', 'N/A')}, 测试={r.get('test_metric', 'N/A')}"
            for i, r in enumerate(trial_results)
        )
        return (
            "你是验证者。请严格审查以下试验结果：\n"
            f"\n假设: {hypothesis_prediction}"
            f"\n校正后 alpha: {adjusted_alpha}"
            f"\n项目内总试验数: {total_trials_in_project}"
            f"\n\n结果:\n{results_summary}"
            "\n\n请评估："
            "\n1. 显著结果是否经得起多重检验校正"
            "\n2. 样本外（测试期）表现是否稳定"
            "\n3. 是否存在过拟合风险"
            "\n4. 效应量的实际意义"
            "\n5. 是否需要重新执行试验"
            "\n\n使用 [VALIDATION_VERDICT] 标签给出最终判定。"
        )

    @staticmethod
    def build_report_prompt(
        research_question: str,
        hypothesis: dict[str, Any],
        trial_plans: list[dict[str, Any]],
        trial_results: list[dict[str, Any]],
        governance_stats: dict[str, Any],
    ) -> str:
        """Build prompt for Stage 6: Report generation."""
        return (
            "你是研究报告撰写者。请基于以下完整研究流程生成结构化报告：\n"
            f"\n研究问题: {research_question}"
            f"\n\n假设: {hypothesis.get('prediction', '')}"
            f"\n因子: {', '.join(hypothesis.get('factor_names', []))}"
            f"\n\n试验数量: {len(trial_plans)}"
            f"\n治理统计: 总试验={governance_stats.get('total_trials', 0)}, "
            f"显著={governance_stats.get('significant_count', 0)}, "
            f"FWER={governance_stats.get('family_wise_error_rate', 0):.4f}"
            "\n\n请包含以下章节："
            "\n1. 摘要"
            "\n2. 研究背景与假设"
            "\n3. 试验设计"
            "\n4. 结果分析"
            "\n5. 多重检验校正说明"
            "\n6. 局限性"
            "\n7. 结论与建议"
            "\n\n使用 [REPORT_SECTION] 标签包裹每个章节。"
        )

    @staticmethod
    def parse_structured_output(response: str, tag: str) -> list[str]:
        """Extract tagged sections from AI response."""
        import re
        pattern = rf"\{tag}(.*?)(?=\{tag}|\Z)"
        matches = re.findall(pattern, response, re.DOTALL)
        return [m.strip() for m in matches if m.strip()]
