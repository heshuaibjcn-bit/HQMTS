"""Seed test DB with raw SQL for speed and simplicity."""
import sqlite3
import json
from datetime import datetime, timedelta, timezone

DB = "test_qa.db"
NOW = datetime.now(timezone(timedelta(hours=8)))
DT = lambda minutes_ago=0: (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S")

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

# Drop and recreate
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in tables:
    conn.execute(f"DROP TABLE IF EXISTS [{t}]")
conn.commit()

# Use SQLAlchemy to create all tables via ORM
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from hqmts.db.base import Base
# Import all models to register them
import hqmts.db.models.user
import hqmts.db.models.instrument
import hqmts.db.models.bar
import hqmts.db.models.account
import hqmts.db.models.position
import hqmts.db.models.strategy
import hqmts.db.models.signal
import hqmts.db.models.decision
import hqmts.db.models.feature
import hqmts.db.models.risk
import hqmts.db.models.execution
import hqmts.db.models.order
import hqmts.db.models.trade
import hqmts.db.models.reservation
import hqmts.db.models.audit
import hqmts.db.models.alert
import hqmts.db.models.approval_request
import hqmts.db.models.agent_task
import hqmts.db.models.agent_proposal
import hqmts.db.models.tool_invocation
import hqmts.db.models.controlled_execution
import hqmts.db.models.chat
import hqmts.db.models.backtest
import hqmts.db.models.admission
import hqmts.db.models.version
import hqmts.db.models.external_event
import hqmts.db.models.recovery
import hqmts.db.models.reconciliation
import hqmts.db.models.correction

async def create_tables():
    engine = create_async_engine(f"sqlite+aiosqlite:///{DB}", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

asyncio.run(create_tables())
print("Tables created via ORM")

# Reconnect after async engine closes
conn = sqlite3.connect(DB)
c = conn.cursor()

# ── Users ──
import bcrypt as _bcrypt
_admin_hash = _bcrypt.hashpw(b"admin123", _bcrypt.gensalt()).decode()
_trader_hash = _bcrypt.hashpw(b"trader123", _bcrypt.gensalt()).decode()
_research_hash = _bcrypt.hashpw(b"research123", _bcrypt.gensalt()).decode()
c.executemany("INSERT INTO users (user_id, username, password_hash, role, display_name, is_active) VALUES (?,?,?,?,?,?)", [
    ("user_admin001", "admin", _admin_hash, "system_admin", "系统管理员", 1),
    ("user_trader001", "trader", _trader_hash, "trader", "交易员", 1),
    ("user_research001", "researcher", _research_hash, "quant_researcher", "量化研究员", 1),
    ("user_risk001", "riskmgr", _bcrypt.hashpw(b"risk123", _bcrypt.gensalt()).decode(), "risk_manager", "风控经理", 1),
    ("user_audit001", "auditor", _bcrypt.hashpw(b"audit123", _bcrypt.gensalt()).decode(), "auditor", "审计员", 1),
])

# ── Instruments ──
c.executemany("INSERT INTO instruments (instrument_id, ts_code, exchange, symbol, name, listing_status, board_type, is_st, lot_size, upper_limit_rule, lower_limit_rule, sector, industry, is_index, constituent_of, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
    ("inst_600519", "600519.SH", "SSE", "600519", "贵州茅台", "L", "mainboard", 0, 100, "normal", "normal", "消费", "白酒", 0, "", DT(0), DT(0)),
    ("inst_000858", "000858.SZ", "SZSE", "000858", "五粮液", "L", "mainboard", 0, 100, "normal", "normal", "消费", "白酒", 0, "", DT(0), DT(0)),
    ("inst_601318", "601318.SH", "SSE", "601318", "中国平安", "L", "mainboard", 0, 100, "normal", "normal", "金融", "保险", 0, "", DT(0), DT(0)),
    ("inst_000001", "000001.SZ", "SZSE", "000001", "平安银行", "L", "mainboard", 0, 100, "normal", "normal", "金融", "银行", 0, "", DT(0), DT(0)),
    ("inst_600036", "600036.SH", "SSE", "600036", "招商银行", "L", "mainboard", 0, 100, "normal", "normal", "金融", "银行", 0, "", DT(0), DT(0)),
    ("inst_000333", "000333.SZ", "SZSE", "000333", "美的集团", "L", "mainboard", 0, 100, "normal", "normal", "消费", "家电", 0, "", DT(0), DT(0)),
])

# ── Account ──
c.execute("INSERT INTO accounts (account_id, total_asset, available_cash, frozen_cash, market_value, pnl_intraday, drawdown_intraday, currency, risk_status, updated_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    ("acc_001", 1523456.78, 523456.78, 50000.00, 950000.00, 12345.67, 0.0081, "CNY", "normal", DT(0), DT(0)))

# ── Positions ──
c.executemany("INSERT INTO positions (account_id, instrument_id, total_quantity, available_quantity, frozen_quantity, cost_price, market_value, market_price, realized_pnl, strategy_instance_id, updated_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
    ("acc_001", "inst_600519", 500, 400, 100, 1680.50, 840250.00, 1750.20, 34850.00, "si_001", DT(0), DT(0)),
    ("acc_001", "inst_000858", 1000, 800, 200, 145.30, 145300.00, 152.80, 7500.00, "si_001", DT(0), DT(0)),
    ("acc_001", "inst_601318", 2000, 2000, 0, 48.20, 96400.00, 47.85, -700.00, "si_002", DT(0), DT(0)),
    ("acc_001", "inst_000001", 5000, 3000, 2000, 12.50, 62500.00, 12.68, 900.00, "si_002", DT(0), DT(0)),
    ("acc_001", "inst_600036", 1000, 0, 1000, 35.20, 35200.00, 35.45, 250.00, "si_003", DT(0), DT(0)),
])

# ── Strategies ──
c.executemany("INSERT INTO strategies (strategy_id, name, version, description, supported_cycles, param_schema_json, default_params_json, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", [
    ("strat_001", "分钟动量突破", "v1.2.0", "基于5分钟K线的动量突破策略，使用布林带和成交量确认",
     json.dumps(["5m"]), json.dumps({"bb_period": 20, "bb_std": 2.0}), json.dumps({"bb_period": 20, "bb_std": 2.0, "vol_mult": 1.5}), "active", DT(120), DT(0)),
    ("strat_002", "跨周期均线策略", "v1.0.0", "5m/15m双周期均线交叉策略",
     json.dumps(["5m", "15m"]), json.dumps({"fast_period": 10, "slow_period": 30}), json.dumps({"fast_period": 10, "slow_period": 30}), "active", DT(200), DT(0)),
    ("strat_003", "均值回复策略", "v0.8.0", "基于Z-Score的均值回复策略",
     json.dumps(["5m"]), json.dumps({"lookback": 60, "z_threshold": 2.0}), json.dumps({"lookback": 60, "z_threshold": 2.0}), "draft", DT(50), DT(0)),
])

# ── Strategy Instances ──
c.executemany("INSERT INTO strategy_instances (strategy_instance_id, strategy_id, strategy_version, environment, status, params_json, instruments_json, account_id, cycle, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
    ("si_001", "strat_001", "v1.2.0", "live", "live_running", json.dumps({"bb_period":20,"bb_std":2.0}), json.dumps(["inst_600519","inst_000858"]), "acc_001", "5m", DT(100), DT(0)),
    ("si_002", "strat_002", "v1.0.0", "live", "live_running", json.dumps({"fast_period":10,"slow_period":30}), json.dumps(["inst_601318","inst_000001"]), "acc_001", "5m", DT(100), DT(0)),
    ("si_003", "strat_001", "v1.2.0", "paper", "paper_running", json.dumps({"bb_period":20,"bb_std":2.0}), json.dumps(["inst_600036"]), "acc_001", "5m", DT(30), DT(0)),
])

# ── Signals ──
c.executemany("INSERT INTO signals (signal_id, strategy_instance_id, strategy_version, decision_time, instrument_id, signal_type, target_direction, target_position, signal_strength, valid_until, reason_code, cycle, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
    ("sig_001", "si_001", "v1.2.0", DT(15), "inst_600519", "entry", "long", 500, 0.85, DT(-60), "bb_breakout_up", "5m", DT(15), DT(0)),
    ("sig_002", "si_001", "v1.2.0", DT(10), "inst_000858", "entry", "long", 1000, 0.72, DT(-60), "vol_surge", "5m", DT(10), DT(0)),
    ("sig_003", "si_002", "v1.0.0", DT(8), "inst_601318", "entry", "short", 2000, 0.65, DT(-60), "ma_cross_down", "5m", DT(8), DT(0)),
    ("sig_004", "si_002", "v1.0.0", DT(5), "inst_000001", "entry", "long", 5000, 0.78, DT(-60), "ma_cross_up", "5m", DT(5), DT(0)),
    ("sig_005", "si_003", "v1.2.0", DT(3), "inst_600036", "entry", "long", 1000, 0.55, DT(-60), "bb_breakout_up", "5m", DT(3), DT(0)),
])

# ── Risk Checks ──
c.executemany("INSERT INTO risk_check_results (risk_check_id, signal_id, result_type, resized_quantity, reject_reason, triggered_rules_json, check_time, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)", [
    ("rc_001", "sig_001", "allow", None, "", json.dumps(["market_normal","account_ok"]), DT(14), DT(14), DT(0)),
    ("rc_002", "sig_002", "allow", None, "", json.dumps(["market_normal"]), DT(9), DT(9), DT(0)),
    ("rc_003", "sig_003", "allow", None, "", json.dumps(["market_normal"]), DT(7), DT(7), DT(0)),
    ("rc_004", "sig_004", "resize", 3000, "", json.dumps(["account_position_limit"]), DT(4), DT(4), DT(0)),
    ("rc_005", "sig_005", "reject", None, "paper环境信号不进入实盘", json.dumps(["environment_check"]), DT(2), DT(2), DT(0)),
])

# ── Orders ──
c.executemany("INSERT INTO orders (order_id, order_request_id, broker_order_id, account_id, instrument_id, side, price, quantity, order_type, signal_id, execution_intent_id, action_id, status, submitted_time, updated_time, filled_quantity, avg_fill_price, reject_reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
    ("ord_001", "oreq_001", "B20250418001", "acc_001", "inst_600519", "buy", 1680.50, 500, "limit", "sig_001", "ei_001", "act_001", "filled", DT(12), DT(10), 500, 1680.50, "", DT(12), DT(10)),
    ("ord_002", "oreq_002", "B20250418002", "acc_001", "inst_000858", "buy", 145.30, 1000, "limit", "sig_002", "ei_002", "act_002", "partial_filled", DT(8), DT(5), 600, 145.80, "", DT(8), DT(5)),
    ("ord_003", "oreq_003", "B20250418003", "acc_001", "inst_601318", "sell", 48.20, 2000, "limit", "sig_003", "ei_003", "act_003", "submitted", DT(6), DT(6), 0, 0, "", DT(6), DT(6)),
    ("ord_004", "oreq_004", "B20250418004", "acc_001", "inst_000001", "buy", 12.50, 3000, "limit", "sig_004", "ei_004", "act_004", "pending_submit", DT(3), DT(3), 0, 0, "", DT(3), DT(3)),
    ("ord_005", None, None, "acc_001", "inst_000333", "buy", 52.10, 500, "limit", None, None, None, "rejected", DT(60), DT(60), 0, 0, "insufficient_cash", DT(60), DT(60)),
    ("ord_006", None, None, "acc_001", "inst_600036", "sell", 35.20, 1000, "limit", None, None, None, "canceled", DT(120), DT(120), 0, 0, "user_cancel", DT(120), DT(120)),
])

# ── Trades ──
c.executemany("INSERT INTO trades (trade_id, order_id, instrument_id, traded_at, trade_price, trade_quantity, commission, stamp_tax, slippage, broker_trade_id) VALUES (?,?,?,?,?,?,?,?,?,?)", [
    ("trade_001", "ord_001", "inst_600519", DT(11), 1680.50, 500, 2.52, 0.84, 0.00, "BT_20250418_001"),
    ("trade_002", "ord_002", "inst_000858", DT(7), 145.60, 400, 0.58, 0.00, 0.10, "BT_20250418_002"),
    ("trade_003", "ord_002", "inst_000858", DT(5), 145.95, 200, 0.29, 0.00, 0.10, "BT_20250418_003"),
])

# ── Alerts ──
c.executemany("INSERT INTO alerts (alert_id, rule_name, level, metric, value, threshold, message, acknowledged, detected_at, routing_target) VALUES (?,?,?,?,?,?,?,?,?,?)", [
    ("alert_001", "daily_loss_check", "P1", "pnl_intraday", 0.008, 0.02, "日内回撤接近阈值 (0.8% / 2.0%)", 0, DT(30), "trader"),
    ("alert_002", "order_reject_rate", "P2", "reject_rate", 0.15, 0.10, "订单拒绝率偏高 (15% > 10%)", 0, DT(60), "trader"),
    ("alert_003", "qmt_latency", "P2", "latency_ms", 250, 200, "QMT 延迟偏高 (250ms > 200ms)", 1, DT(120), "admin"),
    ("alert_004", "data_quality", "P3", "missing_bars", 3, 0, "3个标的分钟Bar缺失", 0, DT(180), "researcher"),
    ("alert_005", "strategy_drawdown", "P1", "strategy_drawdown", 0.05, 0.03, "策略 si_002 回撤超限 (5% > 3%)", 0, DT(15), "trader"),
])

# ── Audit Events ──
c.executemany("INSERT INTO audit_events (audit_event_id, event_type, entity_type, entity_id, environment, actor, action, details_json, alert_level, correlation_id, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
    ("ae_001", "order_submit", "order", "ord_001", "live", "user_trader001", "submit_order", json.dumps({"instrument":"600519","side":"buy","qty":500}), "info", "corr_001", DT(45)),
    ("ae_002", "risk_check", "signal", "sig_001", "live", "system", "risk_check_pass", json.dumps({"result":"allow"}), "info", "corr_001", DT(44)),
    ("ae_003", "order_fill", "order", "ord_001", "live", "system", "trade_confirmed", json.dumps({"filled_qty":500}), "info", "corr_001", DT(42)),
    ("ae_004", "alert_triggered", "alert", "alert_001", "live", "system", "alert_created", json.dumps({"level":"P1"}), "warning", None, DT(30)),
    ("ae_005", "login", "user", "user_admin001", "live", "user_admin001", "user_login", json.dumps({"ip":"127.0.0.1"}), "info", None, DT(5)),
    ("ae_006", "strategy_state_change", "strategy_instance", "si_003", "paper", "user_trader001", "start_paper", json.dumps({"from":"draft","to":"paper_running"}), "info", None, DT(60)),
])

# ── Approval Requests ──
c.executemany("INSERT INTO approval_requests (approval_request_id, source_type, source_id, approval_type, requested_by, requested_at, approver, decision, decision_reason, approval_snapshot_ref, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
    ("apr_001", "agent_proposal", "prop_001", "live_release", "user_trader001", DT(120), "", "", "", "", DT(120), DT(0)),
    ("apr_002", "kill_switch_deactivate", "ks_deact_001", "kill_switch_deactivate", "user_admin001", DT(60), "", "", "", "", DT(60), DT(0)),
])

# ── Agent Tasks ──
c.executemany("INSERT INTO agent_tasks (agent_task_id, agent_role, task_type, environment, input_ref, output_ref, workflow_version, tool_plan, status, started_at, completed_at, failure_reason, triggered_by, correlation_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
    ("at_001", "Monitoring Agent", "anomaly_detection", "live", json.dumps({"scope":"all_strategies"}), "", "v1.0", json.dumps(["query_positions","query_risk_status"]), "running", DT(5), None, "", "schedule", "corr_agent_001", DT(5), DT(0)),
    ("at_002", "Research Agent", "factor_analysis", "research", json.dumps({"factors":["momentum","volatility"]}), json.dumps({"report":"factor_report_001.html"}), "v1.0", json.dumps(["query_bars","compute_factors"]), "completed", DT(180), DT(120), "", "user_research001", "corr_agent_002", DT(180), DT(120)),
])

# ── Chat Sessions ──
c.executemany("INSERT INTO chat_sessions (chat_session_id, user_id, title, model_provider, environment, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)", [
    ("cs_001", "user_admin001", "持仓分析", "claude", "live", "active", DT(60), DT(10)),
    ("cs_002", "user_admin001", "策略优化讨论", "claude", "research", "idle", DT(1440), DT(300)),
])

# ── Chat Messages ──
c.executemany("INSERT INTO chat_messages (chat_message_id, chat_session_id, role, content, metadata_json, created_at) VALUES (?,?,?,?,?,?)", [
    ("cm_001", "cs_001", "user", "帮我分析一下当前的持仓情况，有没有风险敞口过大的问题？", "", DT(10)),
    ("cm_002", "cs_001", "assistant", "当前持仓分析：\n\n1. **总资产**: ¥1,523,456.78\n2. **持仓集中度**: 贵州茅台占比55.1%，集中度较高\n3. **日内盈亏**: +¥12,345.67 (+0.81%)\n4. **风险提示**: 茅台仓位偏重，建议适当减仓至40%以下\n\n需要我生成具体的调仓建议吗？", "", DT(9)),
    ("cm_003", "cs_002", "user", "动量策略最近的回测表现怎么样？", "", DT(1440)),
    ("cm_004", "cs_002", "assistant", "动量突破策略 (v1.2.0) 最近回测结果：\n\n- 总收益: +18.5%\n- 最大回撤: -6.2%\n- Sharpe Ratio: 1.45\n- 胜率: 62%\n\n表现稳健，建议进入Paper环境验证。", "", DT(1439)),
])

# ── Backtest Results ──
c.executemany("INSERT INTO backtest_results (id, backtest_id, strategy_name, strategy_version, strategy_params, instruments, cycle, start_date, end_date, initial_cash, final_total_asset, total_return, annualized_return, max_drawdown, sharpe_ratio, total_trades, win_rate, profit_factor, trades, daily_values, cost_summary, data_version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
    (1, "bt_001", "分钟动量突破", "v1.2.0", json.dumps({"bb_period":20,"bb_std":2.0}), json.dumps(["600519.SH"]), "5m", "20240101", "20241231", 1000000, 1185000, 0.185, 0.205, -0.062, 1.45, 156, 0.62, 1.85, "[]", "[]", json.dumps({"commission":3500,"slippage":1200,"tax":800}), "tushare_v2024", DT(2880), DT(0)),
    (2, "bt_002", "跨周期均线策略", "v1.0.0", json.dumps({"fast_period":10,"slow_period":30}), json.dumps(["601318.SH"]), "5m", "20240601", "20241231", 500000, 535000, 0.07, 0.12, -0.045, 1.12, 48, 0.58, 1.45, "[]", "[]", json.dumps({"commission":1200,"slippage":600,"tax":300}), "tushare_v2024", DT(7200), DT(0)),
])

# ── Admission Records ──
c.execute("INSERT INTO admission_records (admission_id, strategy_instance_id, strategy_version, paper_total_return_pct, paper_max_drawdown_pct, paper_sharpe_ratio, paper_win_rate_pct, paper_total_trades, paper_trading_days, max_daily_loss_pct, readiness_score, readiness_passed, status, approval_request_id, approver, decision_reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    ("adm_001", "si_003", "v1.2.0", 0.085, -0.035, 1.32, 0.60, 89, 15, -0.012, 0.82, 1, "pending_approval", "apr_001", "", "", DT(120), DT(0)))

conn.commit()
conn.close()
print("\n=== ALL DATA SEEDED ===")
