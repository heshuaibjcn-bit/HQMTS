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
