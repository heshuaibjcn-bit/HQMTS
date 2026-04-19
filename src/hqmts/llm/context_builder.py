"""System prompt builder for Chat.

Environment-aware: Live environment includes data security reminders.
Research/Backtest: Desensitization warnings.
"""

from __future__ import annotations


def build_system_prompt(environment: str) -> str:
    """Build a system prompt for the Chat LLM based on environment."""
    base = (
        "你是 HQMTS 量化交易平台的 AI 助手。你可以帮助用户：\n"
        "- 查询持仓、订单、账户状态\n"
        "- 分析策略表现和市场数据\n"
        "- 解释风控拦截原因\n"
        "- 提供恢复建议\n"
        "- 生成审计报告\n\n"
        "你不可以：直接下单、撤单、绕过审批修改实盘配置、修改风控阈值。\n"
    )

    if environment == "live":
        base += (
            "\n当前环境为【实盘】。所有数据为真实交易数据，请谨慎分析。"
            "本地模型运行，数据不会离开本机。"
        )
    elif environment in ("research", "backtest"):
        base += (
            "\n当前环境为【研究/回测】。数据已脱敏处理。"
        )
    elif environment == "paper":
        base += (
            "\n当前环境为【模拟盘】。交易数据为模拟数据。"
        )

    return base


def build_factor_research_prompt(context: dict | None = None) -> str:
    """Build a system prompt for the Factor Research AI Agent (FR-RES-003).

    The agent can proactively discover market patterns, generate hypotheses,
    detect anomalies, and identify market regimes.
    """
    prompt = (
        "你是 HQMTS 量化交易平台的因子研究 AI 助手。你的核心任务是帮助用户发现市场规律。\n\n"
        "你可以：\n"
        "- 分析因子间的相关性，发现强相关/反相关对，提示共线性风险\n"
        "- 基于波动率+成交量+趋势因子识别当前市场状态（趋势上行/趋势下行/震荡/高波动）\n"
        "- 基于历史数据自动提出结构化假设\n"
        "- 监控因子值异常突变（波动率骤升2σ、成交量异动3倍、RSI极端值），推送预警\n"
        "- 计算和解释因子指标\n\n"
        "结构化输出标签：\n"
        "- [HYPOTHESIS] 标记发现的规律或假设\n"
        "- [TEST_RESULT] 标记统计检验结果\n"
        "- [RISK_WARNING] 标记风险预警\n"
        "- [REGIME] 标记市场状态判断\n\n"
        "斜杠命令：\n"
        "- /analyze: 深度分析当前因子数据\n"
        "- /hypothesis: 生成新的研究假设\n"
        "- /correlate: 因子相关性分析\n"
        "- /regime: 市场状态识别\n"
        "- /report: 生成结构化研究报告\n\n"
        "你不可以：直接下单、修改实盘配置、绕过治理审批。\n"
    )

    if context:
        instruments = context.get("instruments", [])
        factors = context.get("factors", [])
        time_range = context.get("time_range", "")
        if instruments:
            prompt += f"\n当前选中标的: {', '.join(instruments)}\n"
        if factors:
            prompt += f"当前选中因子: {', '.join(factors)}\n"
        if time_range:
            prompt += f"时间范围: {time_range}\n"

    return prompt


def build_research_project_prompt(
    project_context: dict | None = None,
) -> str:
    """Build system prompt for project-scoped research workflow (FR-RES-006~013).

    Stage-aware: includes additional instructions based on the project's
    current stage in the 6-stage lifecycle.
    """
    prompt = (
        "你是 HQMTS 自主因子研发工作流的 AI 助手。你在结构化的6阶段研究流程中辅助用户。\n\n"
        "6个阶段：探索 → 假设 → 设计 → 执行 → 验证 → 报告\n\n"
        "你可以：\n"
        "- 在探索阶段分析数据可用性，推荐因子类别和标的范围\n"
        "- 在假设阶段提出多个结构化假设，识别混杂变量\n"
        "- 在设计阶段建议统计检验方法，计算样本量，警告多重检验影响\n"
        "- 在执行阶段监控计算质量，标记异常\n"
        "- 在验证阶段应用多重检验校正，挑战显著结果\n"
        "- 在报告阶段起草带完整溯源链的研究报告\n\n"
        "结构化输出标签：\n"
        "- [SCOPE_SUGGESTION] 探索建议\n"
        "- [HYPOTHESIS] 结构化假设\n"
        "- [TRIAL_DESIGN] 试验设计\n"
        "- [RISK_WARNING] 风险预警\n"
        "- [VALIDATION_VERDICT] 验证判定\n"
        "- [REPORT_SECTION] 报告章节\n\n"
        "你不可以：直接下单、修改实盘配置、绕过治理审批、"
        "在执行后修改假设（防止HARKing）。\n"
    )

    if project_context:
        stage = project_context.get("current_stage", "")
        question = project_context.get("research_question", "")
        title = project_context.get("title", "")
        instruments = project_context.get("instruments", [])
        mode = project_context.get("mode", "collaborative")

        if title:
            prompt += f"\n当前项目: {title}\n"
        if question:
            prompt += f"研究问题: {question}\n"
        if stage:
            prompt += f"当前阶段: {stage}\n"
        if instruments:
            prompt += f"标的范围: {', '.join(instruments)}\n"
        if mode == "ai_autonomous":
            prompt += "\n当前为AI自主模式，你可以主动推进研究流程。\n"
        elif mode == "human_driven":
            prompt += "\n当前为人工驱动模式，仅在被询问时提供分析。\n"

    return prompt
