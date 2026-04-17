
**文档版本**：V1.3  
**产品名称**：Hermes Quant Minute Trading System  
**产品简称**：HQMTS  
**适用市场**：A股  
**交易周期**：5分钟 / 15分钟 / 30分钟 / 60分钟  
**历史数据源**：Tushare Pro  
**实盘接口**：QMT  
**智能编排层**：Hermes Agent  
**文档状态**：修订版  
**修订说明**：在 V1.1 基础上，进一步明确 Hermes Agent 的系统定位、确定性内核边界、工具权限模型、审批与审计闭环、失败语义与验收要求，避免将 Agent 误用为交易执行内核

---

# 1. 文档目的

本文档用于定义 HQMTS V1.3 的产品目标、系统边界、关键约束、功能需求、治理机制、验收标准与版本规划，用于指导：

- 架构设计
- 技术方案设计
- 研发任务拆解
- 测试设计
- 上线制度设计
- 研究与实盘协同规范
- Hermes Agent 接入边界设计
- 审批与审计制度设计

本 PRD 不仅定义“做什么”，还定义：

- 哪些行为允许自动化
- 哪些行为必须人工审批
- 哪些系统边界不可突破
- 如何保障回测、仿真、实盘一致性
- 如何控制 Agent 的自治风险
- 如何保证交易主路径由确定性内核承载
- 如何让 Agent 行为可审计、可回放、可追责

---

# 2. 产品概述

## 2.1 产品背景

A股分钟级量化系统若要真正落地，必须同时满足五类要求：

1. **研究可持续**
    
    - 能持续挖掘市场规律
    - 能快速研发和迭代策略
    - 能进行严格验证与复现
2. **交易可执行**
    
    - 能接入 QMT 实盘
    - 能处理分钟级实时数据与订单状态
    - 能适配 A股 交易规则
3. **系统可治理**
    
    - 研究自动化与交易自动化边界清晰
    - 策略上线、降级、下线有制度
    - 数据、策略、回测结果可审计、可复现
4. **风险可控制**
    
    - 实盘链路具备独立风控
    - 存在断线重连、对账修复、人工接管能力
    - Agent 不得绕过治理机制直接影响实盘风险
5. **自动化可约束**
    
    - Agent 可用于研究、分析、编排和辅助运维
    - Agent 不得替代交易状态机、风控裁决和执行网关
    - Agent 的所有有副作用行为必须经受控工具链执行并可审计

---

## 2.2 产品目标

构建一套面向 A股 5m / 15m / 30m / 60m 交易的受治理量化平台，支持：

- 基于 **Tushare Pro** 完成历史研究、数据准备和回测；
- 基于 **QMT** 完成实时行情接入和实盘下单；
- 基于 **Hermes Agent** 完成研究流程编排、分析辅助、回测与验证任务调度、优化实验编排、监控分析、报告生成和恢复建议；
- 实现研究—验证—仿真—实盘—反馈—再优化闭环；
- 在满足安全治理前提下，逐步提高自动化程度。

同时明确：

- 核心交易执行、风控裁决、状态迁移、对账修复必须由确定性服务实现；
- Hermes Agent 是受控智能编排层，不是交易确定性内核。

---

## 2.3 产品定位

本系统定位为：

> **一套以研究驱动、以治理约束、以确定性交易内核落地、以 Hermes Agent 提升自动化效率的 A股分钟级智能量化平台**

本系统不是：

- 毫秒级高频系统
- 任意 AI 自动下单系统
- 无人工审批的全自治实盘系统
- 由 Agent 直接主导交易状态流转的系统

---

# 3. 第一性约束

本产品设计必须遵守以下不可突破原则。

## 3.1 研究与交易分离原则

研究系统可以高频试错，交易系统必须低频变更、强约束执行。  
任何研究结论未经准入流程，不得直接进入实盘。

## 3.2 回测、仿真、实盘统一策略接口原则

同一策略逻辑在回测、仿真、实盘中必须使用统一接口与统一核心信号逻辑，不允许维护三套不同策略逻辑。

## 3.3 实盘风控独立原则

风控模块不得依赖策略自觉，必须独立于策略执行，拥有拦截、降级、停机权限。

## 3.4 已完成Bar原则

V1 默认策略仅允许使用 **已完成Bar** 参与正式信号决策。  
未完成Bar数据仅允许用于监控、预警或研究实验，不得直接用于正式实盘决策。

## 3.5 版本可复现原则

任何回测结果、仿真结果、实盘上线决策必须可追溯到：

- 数据版本
- 因子版本
- 策略版本
- 参数版本
- 风控版本
- 执行网关版本
- Agent 工作流版本（如参与研究、评审或建议生成）

## 3.6 人工最终控制原则

所有进入实盘、恢复实盘、修改关键风控阈值、替换执行节点等操作，V1 必须支持人工确认。

## 3.7 确定性内核优先原则

所有直接影响实盘资产、账户余额、订单状态、成交状态、持仓状态、风险暴露和审计结论的关键路径，必须由确定性、可验证、可回放的服务和显式状态机实现。  
Hermes Agent 只能作为编排、分析、建议或受控触发层，不得替代交易确定性内核。

## 3.8 Agent 受控工具原则

Hermes Agent 不得直接访问核心交易状态写接口、不得直接写数据库核心对象、不得直接调用 QMT 下单接口。  
Agent 只能通过白名单 Tool / Control API / Transition API 间接作用系统，且所有有副作用调用必须可审计。

## 3.9 Live 默认失败关闭原则

凡涉及 Live 环境的 Agent 任务、任务触发、审批流和运行辅助行为，默认采用 fail-closed 策略。  
超时、不确定、上下文缺失、工具失败或结果冲突时，不得自动继续执行高风险动作。

---

# 4. 产品范围

## 4.1 V1.3 范围内

1. Tushare Pro 历史数据接入
2. QMT 实时行情与交易接口接入
3. 统一 1 分钟底层数据与多周期聚合
4. 因子研究与市场规律发现框架
5. 分钟级策略开发框架
6. 分钟级回测引擎
7. 仿真交易环境
8. 实盘执行链路
9. 风控系统
10. 监控与告警系统
11. Hermes Agent 研究编排与任务治理
12. Hermes Agent 监控分析、报告生成、恢复建议与对账辅助
13. 策略准入/下线制度
14. 环境隔离与发布流程
15. 审计、日志、版本治理、故障恢复
16. Agent 工具权限模型与审计闭环
17. Agent Proposal / Approval / Controlled Execution 闭环
18. 用户界面子系统（Web Dashboard + AI 对话）

## 4.2 V1.3 不包含

1. Tick 级和盘口级策略交易
2. 毫秒级或超低延迟交易
3. 多券商统一网关
4. 期货、期权、港美股
5. 完全无人工审批的实盘自治
6. Agent 自动修改核心执行代码后直接上线
7. Hermes Agent 直接持有实盘下单能力
8. Hermes Agent 直接写入核心交易状态对象
9. Hermes Agent 替代风控引擎做最终风险裁决
10. Hermes Agent 在无审批条件下自动恢复高风险 Live 策略
11. Hermes Agent memory 替代交易主数据、审计数据或事实账本

---

# 5. 目标用户

## 5.1 量化研究者

需要：

- 快速研究规律
- 自动化实验
- 可信回测与验证
- 研究结果可复现
- Agent 辅助生成研究报告与实验编排

## 5.2 量化交易执行者

需要：

- 安全接入实盘
- 实时下单与订单跟踪
- 风控拦截
- 异常告警与人工接管
- Agent 提供异常解释与恢复建议

## 5.3 系统管理者

需要：

- 管理策略版本
- 审批上线流程
- 查看运行状态
- 审计所有关键行为
- 追踪 Agent 调用、Proposal、审批和执行结果

---

# 6. 非目标与边界

以下内容不是 V1.3 的目标：

1. 追求最高频率、最低延迟
2. 让 Agent 自主决定所有实盘行为
3. 一开始就构建多资产全品类平台
4. 一开始就构建复杂深度学习在线训练系统
5. 一开始就支持任意自由代码策略的自动上线
6. 让 Agent 成为实盘主路径中的最终状态决策者
7. 让 Agent 直接承担交易状态恢复的最终执行权

---

# 7. 自治边界与审批机制

本章定义 Hermes Agent 在 V1.3 中的自治边界。

## 7.1 总体原则

- Agent 可以自动化研究、分析、报告、回测、优化、监控、对账分析和恢复建议。
- Agent 可以提出建议，但不允许绕过准入、审批和风控直接改变实盘风险暴露。
- 实盘相关关键动作必须纳入审批或预定义规则约束。
- Agent 的一切有副作用动作必须通过受控工具触发并进入审计闭环。

## 7.2 Agent 行为分层

### L1：只读分析型

允许行为：

- 查询行情、数据质量、回测结果
- 查询订单、成交、持仓、账户快照
- 查询日志、审计、监控、对账结果
- 生成报告、总结、根因分析、异常解释

约束：

- 无写权限
- 无副作用
- 可自动执行

### L2：受限建议型

允许行为：

- 生成因子候选
- 生成策略候选
- 生成参数建议
- 生成仿真建议
- 生成上线建议
- 生成降级建议
- 生成恢复步骤建议
- 生成对账修复建议

约束：

- 输出必须为结构化 proposal
- 不得直接落入生产状态变更
- 需规则引擎或人工确认

### L3：受控触发型

允许行为：

- 发起数据更新任务
- 发起回测任务
- 发起验证任务
- 发起仿真任务
- 发起对账任务
- 发起恢复分析流程
- 在预定义规则下触发 pause_open
- 在预定义规则下触发 close_only
- 创建审批请求

约束：

- 只能调用白名单工具
- 必须经过 policy enforcement
- 必须全量审计
- 必须具备幂等上下文和 correlation_id

### L4：禁止自治型

禁止行为：

- 直接下单
- 直接撤单
- 直接修改 Live 风控关键阈值
- 直接写交易核心表
- 直接恢复高风险策略到 live_running
- 直接修改账户风险上限
- 直接绕过状态机修正订单、成交、持仓状态
- 直接处理未经审批的 correction 生效

## 7.3 自治动作矩阵

|动作|Agent自动执行|需人工审批|禁止自动执行|
|---|---|---|---|
|发起数据更新|是|否|否|
|发起因子研究|是|否|否|
|生成候选策略|是|否|否|
|发起回测|是|否|否|
|发起验证与优化|是|否|否|
|生成仿真上线建议|是|否|否|
|切换策略到仿真环境|可配置|是|否|
|创建实盘上线审批请求|是|否|否|
|切换策略到实盘环境|否|是|否|
|修改实盘风控阈值|否|是|否|
|自动暂停某策略开仓|是|否|否|
|自动触发仅平仓模式|是|否|否|
|自动恢复策略正常交易|否|是|否|
|自动新增实盘账户|否|是|否|
|自动生成自由代码并直接上线|否|否|是|
|直接调用 QMT 下单|否|否|是|
|直接写入交易状态表|否|否|是|

## 7.4 审批对象

V1.3 中，以下动作必须人工审批：

- 新策略进入实盘
- 已下线策略恢复实盘
- 关键风控参数变更
- Kill Switch 停用（激活无需审批，但停用必须审批以防止风险敞口）
- 执行节点切换
- 账户级风险上限调整
- 黑名单/白名单策略级例外配置
- Live 配置修改
- 高风险 correction 生效
- 非标准恢复动作执行

---

# 8. 环境隔离与发布流程

## 8.1 环境定义

系统至少分为四类环境：

1. **Research**
    
    - 研究、因子开发、规律发现、实验编排
2. **Backtest**
    
    - 历史回测与验证
3. **Paper**
    
    - 准实盘仿真，接实时行情，不真实下单
4. **Live**
    
    - 正式实盘

## 8.2 隔离要求

- Research 不可直连 Live 下单能力
- Backtest 不可复用 Live 账户凭证
- Paper 与 Live 使用不同配置和独立运行标识
- Live 环境配置变更需留痕审计
- Live 环境中仅允许白名单策略运行
- 非 Live Agent 上下文不得包含 Live 敏感凭证
- Agent 不得跨环境复用未经授权的记忆和上下文

## 8.3 发布流程

策略上线流程为：

研究通过  
→ 回测通过  
→ 验证通过  
→ 准入评审  
→ Paper 仿真观察  
→ 上线审批  
→ Live 发布  
→ 盘中监控  
→ 盘后复盘  
→ 保留 / 降级 / 下线

## 8.4 Live 变更最低要求

以下内容进入 Live 前必须具备审批单、版本记录和审计留痕：

- 策略版本
- 参数版本
- 风控版本
- QMT 网关版本
- Live 配置版本
- Agent 工作流版本（如影响运行辅助）

---

# 9. 核心领域模型与数据契约

本章定义关键对象的最小契约。详细字段在后续 SAD 与 API 文档中展开。

## 9.1 Instrument

表示证券标的。

最小字段：

- instrument_id
- ts_code
- exchange
- symbol
- name
- listing_status
- board_type
- is_st
- lot_size
- upper_limit_rule
- lower_limit_rule

约束：

- 全系统使用统一证券主键
- 不允许同一标的多格式代码混用

---

## 9.2 Bar

表示 K 线。

最小字段：

- instrument_id
- cycle
- bar_start_time
- bar_end_time
- open
- high
- low
- close
- volume
- amount
- is_completed
- source
- data_version

关键约束：

1. 所有正式策略决策只允许使用 `is_completed = true` 的 Bar
2. `bar_end_time` 为该 Bar 完成时间
3. 系统内部以 1m 为分钟级主真源
4. 5m/15m/30m/60m 由系统统一聚合生成
5. 历史与实时 Bar 字段语义必须一致

---

## 9.3 FeatureSnapshot

表示某时点策略可见特征快照。

最小字段：

- instrument_id
- decision_time
- cycle
- feature_set_version
- feature_values
- source_bar_versions

约束：

- 特征计算必须可复现
- 必须记录依赖的原始Bar版本

---

## 9.4 Signal

表示策略在某时点输出的交易意图。

最小字段：

- signal_id
- strategy_id
- strategy_version
- decision_time
- instrument_id
- signal_type
- target_direction
- target_position
- signal_strength
- valid_until
- reason_code
- feature_snapshot_ref

约束：

- Signal 只表示交易意图，不代表最终订单
- 所有 Signal 必须可追踪到策略版本与特征快照
- Signal 必须具有有效期，过期信号不可执行

---

## 9.5 OrderRequest

表示下单请求。

最小字段：

- order_request_id
- signal_id
- action_id
- account_id
- instrument_id
- side
- order_type
- price
- quantity
- tif
- submit_time
- idempotency_key

约束：

- 所有订单请求必须携带幂等键
- 同一 action_id 不允许重复提交相同意图订单

---

## 9.6 Order

表示券商受理后的委托对象。

最小字段：

- order_id
- order_request_id
- broker_order_id
- status
- submitted_time
- updated_time
- filled_quantity
- avg_fill_price
- reject_reason

订单状态最小状态机：

- created
- pending_submit
- submitted
- partial_filled
- filled
- canceled
- rejected
- expired

---

## 9.7 Trade

表示成交记录。

最小字段：

- trade_id
- order_id
- instrument_id
- trade_time
- trade_price
- trade_quantity
- commission
- tax

---

## 9.8 Position

表示持仓状态。

最小字段：

- account_id
- instrument_id
- total_quantity
- available_quantity
- frozen_quantity
- cost_price
- market_value
- last_update_time

关键约束：

- total_quantity 与 available_quantity 必须区分
- A股 T+1 导致买入当日 available_quantity 可能小于 total_quantity

---

## 9.9 Account

表示账户状态。

最小字段：

- account_id
- total_asset
- available_cash
- frozen_cash
- market_value
- pnl_intraday
- drawdown_intraday
- risk_status
- last_update_time

---

## 9.10 RiskCheckResult

表示风控审查结果。

最小字段：

- risk_check_id
- signal_id / order_request_id
- result_type
- resized_quantity
- reject_reason
- triggered_rules
- check_time

结果类型：

- allow
- reject
- resize
- delay
- force_flatten

---

## 9.11 AgentTask

表示 Hermes Agent 发起的一次任务。

最小字段：

- agent_task_id
- agent_role
- task_type
- environment
- input_ref
- output_ref
- workflow_version
- tool_plan
- status
- started_at
- completed_at
- failure_reason
- triggered_by
- correlation_id

约束：

- 每次 Agent 任务必须具备唯一追踪 ID
- 必须可关联到调用人、调度计划或系统事件
- Live 相关任务必须明确记录环境与工作流版本

---

## 9.12 AgentProposal

表示 Agent 输出的建议，而不是最终执行动作。

最小字段：

- proposal_id
- proposal_type
- source_agent_task_id
- target_object_type
- target_object_id
- proposal_payload
- confidence
- policy_result
- approval_status
- executed_result
- created_at

约束：

- Agent 建议必须与实际执行动作解耦
- 未审批 proposal 不得自动落地到 Live 核心对象

---

## 9.13 ToolInvocation

表示一次 Agent 工具调用。

最小字段：

- invocation_id
- agent_task_id
- tool_name
- tool_version
- input_digest
- output_digest
- side_effect_level
- started_at
- finished_at
- status
- error_code

约束：

- 所有有副作用的 tool 调用必须审计
- tool 调用必须可追溯到 AgentTask
- Live 相关调用必须记录 policy check 结果

---

## 9.14 ApprovalRequest

表示需要人工审批的请求。

最小字段：

- approval_request_id
- source_type
- source_id
- approval_type
- requested_by
- requested_at
- approver
- approved_at
- decision
- decision_reason

约束：

- 审批请求必须关联明确对象和目标动作
- 审批结果必须可追溯到执行结果

---

## 9.15 RecoverySession

表示一次恢复会话。

最小字段：

- recovery_session_id
- scope_type
- scope_id
- trigger_reason
- current_state_snapshot_ref
- proposed_actions_ref
- approval_required
- final_result
- started_at
- completed_at

---

## 9.16 ReconciliationSession

表示一次对账会话。

最小字段：

- reconciliation_session_id
- scope_type
- scope_id
- expected_snapshot_ref
- broker_snapshot_ref
- diff_summary
- severity
- resolution_status
- started_at
- completed_at

---

# 10. 时间驱动与信号生效规则

这是 V1.3 的核心约束之一。

## 10.1 系统主时钟

V1.3 以分钟事件驱动为主。  
所有分钟级策略的正式决策时间点基于 **目标周期Bar完成时刻**。

## 10.2 已完成Bar规则

- 5m 策略仅在 5m Bar 完成时生成正式信号
- 15m 策略仅在 15m Bar 完成时生成正式信号
- 30m / 60m 同理
- 多周期策略引用高周期数据时，只允许使用该周期最近一个已完成Bar

## 10.3 执行时点规则

V1.3 默认执行规则：

- 某周期Bar在 `T` 时刻完成
- 策略在 `T` 生成信号
- 最早在 `T` 之后提交订单
- 回测默认以下一可交易Bar执行成交近似

## 10.4 未完成Bar使用规则

- 未完成Bar仅可用于监控、预警或研究实验
- 未完成Bar不得作为正式信号依据进入实盘链路
- 若未来支持 intrabar 模式，需另立版本与准入标准

## 10.5 交易时段规则

必须显式考虑：

- 上午交易时段
- 午间休市
- 下午交易时段
- 收盘前特殊限制
- 节假日与非交易日

---

# 11. 数据管理子系统

## 11.1 目标

构建统一、可校验、可增量更新、可复现的数据底座。

## 11.2 功能需求

### FR-DATA-001 历史数据接入

支持通过 Tushare Pro 获取：

- 股票基础信息
- 交易日历
- 日线行情
- 分钟级行情
- 指数数据
- 复权因子
- 财务与辅助数据（按可用权限）

### FR-DATA-002 实时数据接入

支持通过 QMT 获取：

- 实时行情
- 实时分钟数据或构建分钟Bar所需事件
- 账户
- 持仓
- 委托
- 成交

### FR-DATA-003 底层真源约束

系统内部以 **1分钟Bar** 作为分钟级统一主真源。  
5m/15m/30m/60m 原则上统一由系统聚合生成。

### FR-DATA-004 数据标准化

统一：

- 证券代码
- 时间戳
- 单位
- 字段名
- 停牌标记
- 复权标记
- 数据版本

### FR-DATA-005 数据质量校验

必须支持：

- 缺失检测
- 重复检测
- 时序连续性检测
- 交易日对齐检测
- 极值异常检测
- 停牌与涨跌停校验

### FR-DATA-006 数据版本管理

必须支持：

- 原始数据版本
- 清洗后数据版本
- 聚合后数据版本
- 回测绑定数据快照

### FR-DATA-007 数据修复

支持指定标的、指定日期、指定周期回溯修复。

## 11.3 约束

- 历史数据源与实时数据源口径差异必须可记录
- 任一回测必须绑定数据版本，不允许“漂移回测”
- Agent 可触发数据任务，但不得绕过数据版本治理和质量校验

---

# 12. 因子研究子系统

## 12.1 目标

在受控治理下自动化发现市场规律并输出可验证假设。

## 12.2 功能需求

### FR-RES-001 因子框架

支持趋势、动量、波动、量能、结构、时间、市场状态、跨周期因子。

### FR-RES-002 因子注册与版本管理

每个因子必须具备：

- 因子名
- 版本
- 输入依赖
- 计算窗口
- 适用周期
- 发布状态

### FR-RES-003 规律发现输出标准

Research Agent 输出规律时，必须结构化包含：

- 假设描述
- 适用标的范围
- 适用时间范围
- 触发条件
- 目标变量
- 显著性指标
- 稳定性指标
- 风险提示

### FR-RES-004 多重检验治理

系统应记录：

- 每轮研究尝试数
- 假设命中数
- 被拒绝假设
- 测试集使用情况

### FR-RES-005 研究报告

系统自动输出图表、统计结果、显著性说明和风险提示。

## 12.3 约束

- 样本外数据不得用于反向调参而不重置实验
- Agent 自动研究必须完整留痕
- 研究产物进入策略开发前必须形成结构化结论，不得以自然语言结论直接驱动实盘变更

---

# 13. 策略开发子系统

## 13.1 目标

将研究结果转化为统一可执行的策略对象。

## 13.2 功能需求

### FR-STR-001 策略模板

V1.3 支持：

- 趋势策略
- 均值回复策略
- 突破策略
- 跨周期过滤策略
- 横截面评分策略

### FR-STR-002 统一策略接口

必须定义统一接口：

- on_init
- on_bar
- generate_signal
- post_signal_check
- on_order_update
- on_trade_update
- on_stop

### FR-STR-003 受控策略表达

V1.3 默认采用：

- 受控模板 + 参数配置
- 可审查规则组合
- 限制直接生成自由执行代码

### FR-STR-004 参数治理

支持：

- 参数默认值
- 合法范围
- 参数版本
- 参数依赖
- 参数实验记录

### FR-STR-005 策略状态机

策略至少具备以下状态：

- draft
- backtest_ready
- validation_ready
- paper_running
- live_running
- pause_open
- close_only
- stopped
- frozen

## 13.3 约束

- 任一 live_running 策略必须绑定唯一版本
- 运行中策略不得被热修改核心逻辑
- Agent 可生成策略候选和参数建议，但不得直接将自由代码策略推入 Live

---

# 14. 回测与仿真子系统

## 14.1 目标

提供尽可能一致、可复现、适配 A股 规则的验证环境。

## 14.2 功能需求

### FR-BT-001 分钟级回测

支持：

- 单标的
- 多标的
- 多周期
- 多策略

### FR-BT-002 A股规则建模

支持模拟：

- T+1
- 涨跌停限制
- 停牌
- 手续费
- 印花税
- 最小交易单位
- 午间休市

### FR-BT-003 撮合规则

V1.3 至少支持：

- 下一可交易Bar开盘近似成交
- 限价单基于Bar范围的近似判断
- 涨跌停不可成交约束
- 不足手数自动修正或拒绝

### FR-BT-004 容量与流动性限制

应支持基础容量约束：

- 最小成交额门槛
- 单笔下单金额限制
- 当Bar成交量占比上限近似

### FR-BT-005 仿真交易

定义两类仿真：

1. 研究仿真：全虚拟
2. 准实盘仿真：接QMT实时行情、完整执行链路、虚拟下单

### FR-BT-006 回测结果留存

结果必须保存：

- 策略版本
- 参数版本
- 数据版本
- 交易明细
- 成本模型
- 报告

## 14.3 约束

- 回测不等于实盘保证
- 对突破类策略必须提示成交近似偏差风险
- Agent 可编排回测任务，但不得绕过结果留存和版本绑定

---

# 15. 验证与优化子系统

## 15.1 目标

控制过拟合并在实盘可执行约束下优化策略。

## 15.2 功能需求

### FR-VAL-001 样本内外验证

支持：

- 样本内
- 样本外
- 时间切片

### FR-VAL-002 Walk-forward

支持滚动训练、滚动测试。

### FR-VAL-003 参数稳定性分析

输出参数热图、稳定区、敏感区。

### FR-VAL-004 成本压力测试

支持不同：

- 滑点
- 手续费
- 成交率假设

### FR-VAL-005 扰动测试

支持：

- 信号延迟
- 价格扰动
- 成交扰动
- 序列重排

### FR-VAL-006 优化算法

支持：

- Grid Search
- Random Search
- Bayesian Optimization
- Genetic Algorithm

### FR-VAL-007 统一目标函数

优化目标不得只追求收益，应纳入：

- 收益
- 回撤
- 稳定性
- 换手
- 成本
- 容量
- 参数平滑性

## 15.3 约束

- 样本外数据禁止直接用于反向优化而不重新切分
- 优化器输出必须伴随过拟合风险评估
- Agent 输出的优化建议必须可追溯到实验批次和目标函数版本

---

# 16. 策略准入与下线制度

这是 V1.3 的核心治理章节之一。

## 16.1 准入级别

策略状态按准入分为：

- 候选
- 可回测
- 可验证
- 可仿真
- 可实盘

## 16.2 实盘准入基本要求

策略进入实盘前，至少满足以下条件：

1. 样本内、样本外、walk-forward 均已完成
2. 样本外表现不为显著负值
3. 成本压力测试后仍具备可接受收益风险比
4. 参数存在稳定区，不为尖峰参数
5. Paper 仿真通过观察期
6. 已配置完整风控规则
7. 有明确适用市场状态说明
8. 已绑定版本与审计记录
9. 已经人工审批通过

## 16.3 一票否决项

以下任一情况不得进入实盘：

- 使用未来数据或未完成Bar
- 无法复现回测结果
- 未通过基本风控配置
- 实盘容量明显不足
- 仿真表现与回测偏差严重且无法解释
- 订单行为存在幂等问题
- 研究与验证日志缺失
- Agent 参与生成的上线建议无法回溯到工作流版本和实验记录

## 16.4 下线与降级条件

以下条件可触发降级为 pause_open / close_only / stopped：

- 单日损失超过阈值
- 连续多日表现显著恶化
- 实盘偏差持续超阈
- QMT执行异常频发
- 风控规则频繁触发
- 持仓对账失败
- 数据源异常持续未恢复

---

# 17. 实盘执行子系统

## 17.1 目标

通过 QMT 安全执行实盘订单，并保证状态可追踪、可恢复、可对账。

## 17.2 功能需求

### FR-LIVE-001 QMT接入

支持：

- 账户查询
- 持仓查询
- 委托查询
- 成交查询
- 下单
- 撤单

### FR-LIVE-002 订单幂等保护

每笔信号生成唯一 `action_id` 和 `idempotency_key`，防止重复下单。

### FR-LIVE-003 订单生命周期管理

管理从 signal 到 order_request 到 broker_order 到 trade 的全流程。

### FR-LIVE-004 状态恢复

支持进程重启后：

- 重建账户状态
- 重建持仓状态
- 对账未完成订单
- 恢复策略运行状态

### FR-LIVE-005 持仓对账

定时对比：

- 本地持仓
- QMT持仓

发现不一致时进入告警或人工接管流程。

### FR-LIVE-006 执行日志

必须完整记录信号、风控、下单、回报、异常。

## 17.3 主路径约束

实盘执行主路径为：

**Signal → Risk Check → OrderRequest → Execution Gateway(QMT Adapter) → Broker Order → Trade**

约束：

- Hermes Agent 不直接参与该主路径中的状态写入和最终决策
- Hermes Agent 不直接调用 QMT 下单接口
- Hermes Agent 可对执行异常进行分析、总结和建议，但不得替代执行网关与订单状态机

---

# 18. QMT执行节点约束与容错设计

## 18.1 部署原则

QMT 执行节点应作为 **本地独立执行网关** 部署，不承担复杂研究任务。

## 18.2 节点职责

- 接收经审批允许的实时策略信号
- 获取账户与持仓
- 执行下单与撤单
- 回传订单与成交状态
- 维持本地执行日志

## 18.3 容错要求

必须支持：

- 断线重连
- 进程重启恢复
- 未完成订单重建
- 持仓状态重建
- 时间同步检查
- 下单失败重试策略
- 不可恢复故障进入 close_only 或 stopped

## 18.4 约束

- QMT节点不得直接运行高自由度研究代码
- QMT节点配置变更需审计
- QMT节点异常恢复后，不得自动恢复高风险策略到 live_running，需人工确认
- Hermes Agent 不得直接驻留在执行节点内承担下单决策

---

# 19. 风控子系统

## 19.1 目标

建立独立于策略的多层风控体系。

## 19.2 风控层级顺序

V1.3 风控执行顺序为：

1. 市场级
2. 账户级
3. 策略级
4. 标的级
5. 订单级

## 19.3 功能需求

### FR-RISK-001 市场级风控

支持：

- 指数大跌暂停开仓
- 极端波动停机
- 特殊时段限制

### FR-RISK-002 账户级风控

支持：

- 总仓位上限
- 单日亏损上限
- 日内回撤阈值
- 可用资金下限

### FR-RISK-003 策略级风控

支持：

- 单策略仓位上限
- 连续亏损停机
- 开仓冷却期
- 单策略日损失上限

### FR-RISK-004 标的级风控

支持：

- 单标的最大暴露
- 流动性过滤
- 黑名单
- ST过滤

### FR-RISK-005 订单级风控

支持：

- 非法价格检查
- 最小手数检查
- 重复下单拦截
- 频繁撤单限制

### FR-RISK-006 Kill Switch

支持：

- 全局停机
- 仅平仓
- 禁止新开仓
- 人工接管

## 19.4 风控结果

风控结果必须标准化为：

- allow
- resize
- reject
- delay
- force_flatten

## 19.5 风控与 Agent 边界

- 风控最终裁决由规则引擎或确定性服务完成
- Agent 可做风险分析、阈值建议、异常解释
- Agent 不得替代风控引擎做最终 allow/reject 裁决

---

# 20. 人工接管与故障恢复机制

## 20.1 人工接管场景

以下场景必须支持人工接管：

- QMT异常断连
- 持仓对账失败
- 连续订单拒绝
- 数据延迟严重
- 实盘收益/风险异常
- 策略状态异常
- 手工介入下单后本地状态失真

## 20.2 人工接管能力

系统必须支持：

- 策略切换为 pause_open
- 策略切换为 close_only
- 全局 kill switch
- 手动对账
- 手动补录外部成交
- 手动冻结策略

## 20.3 故障演练要求

V1.3 上线前至少演练：

- QMT重启
- 网络中断
- 行情延迟
- 订单回报延迟
- 本地服务重启
- 人工下单后系统恢复对账

## 20.4 Agent 在恢复流程中的角色

- Agent 可生成恢复步骤建议
- Agent 可归纳受影响对象和异常链路
- Agent 可发起恢复分析任务
- Agent 不得直接执行高风险恢复动作
- 非标准恢复动作必须进入审批流程

---

# 21. 监控与告警子系统

## 21.1 目标

监控数据、策略、执行、账户、节点和系统健康状态。

## 21.2 告警等级

- **P0**：立即停机 / 仅平仓
- **P1**：立即人工介入
- **P2**：盘中关注，收盘处理
- **P3**：信息提醒

## 21.3 功能需求

支持监控：

- 数据延迟与缺失
- Bar聚合异常
- 信号异常频率
- 下单失败率
- 成交率异常
- 持仓不一致
- 账户风险指标
- QMT节点在线状态
- CPU/内存/磁盘/队列积压
- Agent 任务积压、超时、失败率
- Agent tool 调用失败率和越权拦截次数

---

# 22. Hermes Agent 智能编排子系统

## 22.1 目标

在不破坏交易确定性内核的前提下，为研究、验证、监控、对账、恢复和运维场景提供受控智能编排、分析辅助、任务调度和建议生成能力。

## 22.2 系统定位

Hermes Agent 在 HQMTS 中的定位为：

> **受控智能编排层与辅助决策层**

其职责是：

- 编排研究与验证任务
- 生成结构化建议和报告
- 调用白名单工具完成低风险自动化
- 提供异常分析、对账解释和恢复建议

其非职责是：

- 替代交易确定性内核
- 替代风控引擎最终裁决
- 直接参与实盘订单主路径状态写入
- 直接调用真实下单接口

## 22.3 Agent 角色

至少包括：

- Data Agent
- Research Agent
- Strategy Design Agent
- Backtest Orchestration Agent
- Validation Agent
- Optimization Agent
- Portfolio Analysis Agent
- Monitoring Agent
- Reconciliation Agent
- Recovery Copilot Agent
- Audit Reporting Agent
- Orchestrator Agent

## 22.4 Agent 输入输出契约

每个 Agent 必须定义：

- 输入参数
- 输出结构
- 调用工具
- 超时策略
- 重试策略
- 失败回滚策略
- 幂等上下文要求
- 可访问数据范围
- 是否涉及 Proposal / Approval

## 22.5 Tool 分类与权限模型

Tool 分为：

### 1）只读工具

- 查询行情
- 查询回测结果
- 查询订单状态
- 查询日志与监控
- 查询对账差异
- 查询恢复上下文

特点：

- 无副作用
- 可自动调用
- 必须记录调用来源

### 2）任务触发工具

- 发起回测
- 发起验证
- 发起仿真
- 发起对账
- 发起恢复分析
- 创建审批请求
- 发起报告生成

特点：

- 有流程副作用
- 必须具备幂等和 correlation_id
- 必须进入审计闭环

### 3）受控操作工具

- 暂停策略开仓
- 切换 close_only
- 提交 correction proposal
- 生成并提交恢复 proposal

特点：

- 必须经过 policy check
- 必须可回滚或可人工接管
- 必须记录审批状态和执行结果

### 4）禁止工具

- 直接下单
- 直接撤单
- 直接修改数据库核心交易状态
- 直接修改 Live 风控阈值
- 直接恢复 live_running
- 直接修改账户资产事实对象

## 22.6 Orchestrator 权限

Orchestrator 可以：

- 编排研究任务
- 安排回测和验证
- 生成仿真建议
- 生成上线建议
- 触发自动降级
- 发起对账分析和恢复分析

Orchestrator 不可以：

- 绕过审批直接上线实盘
- 绕过风控直接下单
- 自动修改实盘关键风控阈值
- 自动恢复高风险策略到 live_running
- 直接修正核心交易对象事实状态

## 22.7 Agent 失败处理要求

- Agent 超时不得被视为执行成功
- Agent 输出不完整时不得进入生产副作用步骤
- 所有可重试任务必须具备幂等上下文
- 多步骤任务中，任何有副作用步骤失败后必须进入补偿或人工接管状态
- Agent 不得通过“重复尝试”触发重复实盘行为
- 对 Live 相关任务，默认失败策略为 fail-closed

## 22.8 Agent 上下文最小化原则

- Live 相关 Agent 仅允许读取完成任务所需最小上下文
- 不得将敏感凭证暴露给通用 Agent 上下文
- 不得将未经脱敏的账户敏感信息注入非必要任务
- Agent memory 不得替代系统主数据、审计系统或事实账本

## 22.9 Proposal / Approval / Controlled Execution 闭环

凡 Agent 产生可能导致生产副作用的建议，必须采用以下闭环：

**AgentTask → AgentProposal → Policy Check → ApprovalRequest（如需要）→ Controlled Execution → Audit Record**

任何缺失审批、缺失 policy check、缺失审计的 proposal 不得进入 Live 生效。

---

# 23. 配置、日志、审计与版本治理

## 23.1 目标

确保系统可配置、可回溯、可复现。

## 23.2 配置治理

必须区分：

- 研究配置
- 回测配置
- 仿真配置
- 实盘配置

## 23.3 版本治理对象

必须版本化管理：

- 数据版本
- 因子版本
- 策略版本
- 参数版本
- 成本模型版本
- 风控规则版本
- QMT网关版本
- Agent流程版本
- Tool版本
- Live配置版本

## 23.4 审计要求

必须可追踪：

- 某次实盘上线依据
- 某次订单来源信号
- 某次风控拦截原因
- 某次回测使用的数据版本
- 某次策略变更审批人

## 23.5 Agent 审计治理

必须记录：

- 哪个 Agent 发起了什么任务
- 使用了哪个 workflow version / tool version
- 读取了哪些数据源
- 调用了哪些工具
- 生成了哪些 proposal
- 哪些 proposal 被审批 / 拒绝 / 执行
- 执行结果如何
- 是否存在失败重试与补偿
- 是否触发了越权拦截或 policy rejection

---

# 24. 系统分层建议

为避免实现偏航，HQMTS 采用以下逻辑分层：

## 24.1 数据层

包括：

- Tushare Pro
- QMT 行情/账户/订单数据
- 本地标准化数据仓
- 数据版本与质量校验模块

## 24.2 确定性交易内核

包括：

- 策略运行时
- 风控引擎
- 订单状态机
- QMT 执行网关
- 对账与恢复引擎
- 审计与日志服务

## 24.3 治理与发布层

包括：

- 策略准入
- 审批流
- 配置与版本控制
- 环境隔离
- 发布流程
- Correction 与恢复审批机制

## 24.4 Hermes Agent 智能编排层

包括：

- 研究编排
- 回测编排
- 分析与报告
- 对账分析
- 恢复建议
- 受控任务触发

约束：

- Hermes Agent 位于治理层和内核之外的辅助层
- 不得下沉替代交易确定性内核

---

# 25. 成功标准

## 25.1 业务成功标准

- 研究—回测—验证—仿真—实盘闭环打通
- 至少一类分钟级策略能够稳定通过 Paper 并进入 Live
- Live 交易链路具备可审计和可恢复能力

## 25.2 工程成功标准

- 回测与实盘共享统一策略接口
- Live 环境可重启恢复
- 核心对象契约一致
- 版本链条可追溯
- Agent 调用链条可审计

## 25.3 治理成功标准

- Agent 无法绕过审批与风控
- 所有上线策略均有准入记录
- 所有异常均可定位和追责
- Agent 所有有副作用行为均有工具、审批和审计记录

---

# 26. 验收标准

## 26.1 数据验收

- 指定股票、指定区间历史数据可拉取、校验、入库
- 可生成 5m/15m/30m/60m Bar
- 数据版本可追溯

## 26.2 回测验收

- 支持至少一种跨周期策略完整回测
- 输出交易明细与报告
- 支持 A股 基础规则建模

## 26.3 验证验收

- 支持样本内外和 walk-forward
- 可输出稳健性评分和过拟合风险提示

## 26.4 仿真验收

- 接实时行情
- 信号可生成
- 虚拟订单可流转
- 风控可生效
- 监控可告警

## 26.5 实盘验收

- QMT连接稳定
- 下单、撤单、查询可用
- 幂等保护生效
- 持仓对账可执行
- 异常时可切换人工接管

## 26.6 治理验收

- 审批机制生效
- 策略准入记录完整
- 数据、因子、策略、回测版本可关联查询

## 26.7 Agent 验收

- Agent 无法绕过审批执行 Live 上线
- Agent 无法直接触发真实下单
- Agent 无法直接写入核心交易状态对象
- Agent 的所有 tool 调用可审计
- Agent 发起的 proposal 可追踪到审批与执行结果
- Agent 失败不会导致重复副作用
- Agent 超时、中断、工具失败时进入安全状态
- Agent 对 recovery / reconciliation 的建议可生成但不可越权执行
- 越权尝试会被 policy 拦截并留痕

---

# 27. 风险与假设

## 27.1 风险

1. Tushare Pro 分钟数据口径与完整性风险
2. QMT 节点稳定性风险
3. 回测与实盘成交偏差风险
4. 策略过拟合风险
5. Agent 研究泛滥导致的假阳性风险
6. Agent 工具误配导致的越权或副作用扩大风险
7. 恢复与对账流程复杂度提升带来的运维风险

## 27.2 关键假设

1. 可获取满足研究需求的分钟级历史数据
2. QMT 能满足分钟级交易执行要求
3. 采用已完成Bar规则可支撑当前策略类型
4. 分钟级策略主要依赖规则和因子逻辑，而非毫秒优势
5. Hermes Agent 将以受控工具调用模式接入，而非直接控制交易主路径

---

# 28. 版本规划

## V1.3

重点：明确 Agent 定位、补齐确定性内核边界、权限模型、Proposal/Approval 闭环与失败语义

交付重点：

- 统一核心对象与数据契约
- 回测/仿真/实盘统一接口
- 策略准入与下线制度
- QMT执行节点容错
- 人工接管机制
- Agent治理边界
- AgentTask / Proposal / ToolInvocation / Approval 数据模型
- Tool 权限模型与审计机制
- Agent 验收标准

## V1.5

重点：增强自动化和可用性

交付重点：

- 自动报告
- 更完善的仿真
- 参数优化增强
- 多策略调度增强
- 偏差归因分析
- 对账与恢复建议增强
- 审批流体验优化
- Web Dashboard 核心面板（总览、持仓、订单、风控）
- AI 对话界面（查询类操作、审批流集成）
- WebSocket 实时推送

## V2.0

重点：形成稳定策略工厂

交付重点：

- 多策略组合
- 动态资金分配
- 模型漂移分析
- 更强的自治研究能力
- 更精细的容量与执行建模
- 更完备的 Agent 工具治理体系

---

# 29. 附录：V1.3 核心结论

V1.3 的核心变化不是继续叠加功能，而是进一步把系统从“AI 能参与很多事情的平台”收敛为“**由确定性交易内核承载实盘、由 Hermes Agent 提升研究与运维自动化效率的受治理平台**”。

最关键的 V1.3 设计原则是：

1. 研究自治 ≠ 交易自治
2. 已完成Bar是正式信号唯一依据
3. 交易主路径必须由确定性内核承载
4. Hermes Agent 是智能编排层，不是交易执行内核
5. Agent 只能通过受控工具链作用系统
6. 所有可能导致生产副作用的 Agent 输出必须走 Proposal / Approval / Controlled Execution 闭环
7. 实盘准入与下线必须制度化
8. QMT 只是执行网关，不是研究中心
9. 回测结果必须可复现，实盘行为必须可审计
10. Agent 可以提建议、做分析、发起任务，但不能绕过人和风控

---

# 30. 用户界面子系统

## 30.1 目标

为量化研究者、交易执行者、系统管理者提供可视化操作界面，包括 Web Dashboard 和 AI 对话两种交互方式，使系统从"仅 API 可用"升级为"可视化可操作"。

当前系统所有交互通过 REST API 或 Python SDK 完成，无法直观监控持仓盈亏、风控状态、回测结果，也无法通过自然语言与 Hermes Agent 协作。用户界面子系统旨在填补这一空白。

## 30.2 设计原则

1. **UI 是后端 API 的消费者**，不承载业务逻辑。所有交易决策、风控裁决、状态变更仍由后端确定性服务完成。
2. **Dashboard 与 AI Chat 共享同一套 REST API / WebSocket**，不创建独立数据通道。
3. **支持 4 种环境视角切换**（Research / Backtest / Paper / Live），不同环境展示不同数据范围和操作权限。
4. **实时数据通过 WebSocket 推送**，非实时数据通过 REST API 拉取。
5. **移动端适配**（响应式布局或后续单独 app），V1.5 以桌面端为主。

## 30.3 用户角色与界面权限

| 功能 | 量化研究者 | 交易执行者 | 系统管理者 | 审批要求 |
|------|-----------|-----------|-----------|---------|
| 总览面板 | 只读 | 只读 | 只读 | 无 |
| 持仓管理 | 只读 | 只读 | 只读 | 无 |
| 订单管理 | 查看 | 查看 + 撤单 | 查看 + 撤单 | 撤单需审计（FR-NFR-006） |
| 风控监控 | 查看 | 查看 + Kill Switch | 查看 + Kill Switch + 规则配置 | Kill Switch 可直接激活；**停用需审批**；规则配置走 7.4 审批流 |
| 策略管理 | 创建 + 编辑 | 启停操作 | 全部操作 | **Live 环境启停需审批（7.4）**；Paper 环境自由；创建/编辑不等于部署 |
| 信号监控 | 只读 | 只读 | 只读 | 无 |
| 回测与验证 | 发起回测 + 查看结果 | 查看结果 | 查看结果 | 无 |
| 审计与合规 | 查看自己操作 | 查看相关操作 | 查看全部 | 无 |
| AI 对话 | 研究类 + 分析类 | 监控类 + 操作类 | 全部 | Agent 操作走与 PRD 7.2 相同治理链 |
| 审批操作 | 无 | 审批/拒绝 | 审批/拒绝 | 审批记录进入审计 |

注：前端角色隐藏仅为 UX 优化，安全边界由后端 API 层强制执行。

## 30.4 Web Dashboard 功能需求

### FR-UI-001 总览面板（Overview）

系统首页，一屏展示当前账户全局状态。

展示内容：

- 账户总资产、可用资金、冻结资金、持仓市值
- 日内盈亏（金额 + 百分比）、累计盈亏
- 活跃策略数量及运行状态统计
- 系统健康状态：QMT 连接状态、数据源状态、Agent 状态
- 当前环境标识（Research / Backtest / Paper / Live），醒目区分
- 最新告警（P0/P1 级别置顶）

数据来源：

- `GET /` 系统信息
- `GET /health` 健康状态
- `GET /risk/status` 风控状态
- 账户/持仓聚合数据

### FR-UI-002 持仓管理面板（Positions）

展示内容：

- 持仓列表：标的代码、名称、方向、总数量、可用数量、成本价、现价、市值、浮盈/浮亏（金额 + 百分比）
- T+1 区分：今日买入部分用标识区分，明确不可卖出
- 按策略实例分组查看
- 实时盈亏更新（WebSocket 推送价格变动）

交互：

- 点击持仓查看关联订单和成交明细
- 按标的/策略/盈亏排序和过滤

数据来源：

- 持仓数据（Position ORM）
- 实时行情（QMT 或缓存价格）

### FR-UI-003 订单管理面板（Orders）

展示内容：

- 订单列表：标的、方向（买/卖）、价格、数量、已成交数量、状态、创建时间
- 状态过滤：pending / submitted / partial_filled / filled / canceled / rejected / error
- 订单详情：关联信号、风控检查结果、成交明细、拒绝原因

交互：

- 手动撤单（仅 pending / submitted 状态）
- 点击订单查看完整生命周期（创建→风控→提交→回报→成交）
- 导出订单列表

数据来源：

- `GET /orders/` 订单列表
- `GET /orders/{order_id}` 订单详情
- `GET /risk/checks/{risk_check_id}` 风控检查结果

### FR-UI-004 风控监控面板（Risk）

展示内容：

- 五层风控状态总览：市场级、账户级、策略级、标的级、订单级，各层显示 normal / warning / alert 状态
- 风控检查历史列表（recent_checks）
- Kill Switch 当前状态（活跃/未激活）与激活操作按钮
- Force Flatten 进度查看：触发原因、总持仓数、已平仓数、失败数
- 风控规则配置查看（只读，修改通过审批流）

交互：

- 触发 Kill Switch（需二次确认，通过 REST POST 同步提交，UI 等待 REST 响应确认）
- 停用 Kill Switch（需二次确认 + 审批流 7.4）
- 触发 Force Flatten（需二次确认 + 原因填写，通过 REST POST）
- 查看风控检查详情

数据来源：

- `GET /risk/status` 风控状态
- `GET /risk/checks/{risk_check_id}` 检查详情
- `POST /risk/kill-switch` 激活 Kill Switch（REST 端点，不依赖 WebSocket）
- `POST /risk/kill-switch/deactivate` 停用 Kill Switch（需审批，见 7.4）
- `POST /risk/flatten` 触发平仓
- `GET /risk/flatten/{flatten_id}` 平仓进度

### FR-UI-005 策略管理面板（Strategies）

展示内容：

- 策略列表：名称、版本、描述、创建时间
- 策略实例列表：实例ID、关联策略、运行状态、环境、创建时间
- 策略状态机可视化：显示当前状态及可转换状态（draft → backtest_ready → validation_ready → paper_running → live_running → pause_open / close_only / stopped）

交互：

- 策略状态切换（遵循 PRD 16 章准入制度）
- 查看策略参数配置
- 查看策略关联标的和信号

数据来源：

- `GET /strategies/` 策略列表
- `GET /strategies/{strategy_id}` 策略详情
- `GET /strategies/{strategy_id}/instances` 实例列表

### FR-UI-006 信号监控面板（Signals）

展示内容：

- 实时信号流：策略实例、标的、信号类型（open_long / close_long / open_short / close_short / flatten / hold）、信号强度、决策时间
- 信号详情：关联 Bar 信息、因子快照引用、决策原因码（reason_code）
- 信号历史查询：按策略、标的、时间范围过滤

交互：

- 点击信号查看完整决策链（信号→风控→意图→订单）
- 信号统计分析（按策略/标的聚合）

数据来源：

- `GET /signals/` 信号列表
- `GET /signals/{signal_id}` 信号详情

### FR-UI-007 回测与验证面板（Backtest & Validation）

展示内容：

- 回测任务列表：策略名称、版本、参数、标的、时间范围、状态、创建时间
- 回测结果展示：
  - 收益曲线（净值随时间变化）
  - 回撤曲线（最大回撤标注）
  - 月度/年度收益热力图
  - 交易明细表（时间、标的、方向、价格、数量、盈亏）
  - 关键指标卡片：总收益、年化收益、最大回撤、Sharpe Ratio、胜率、盈亏比、总交易次数
- 参数优化结果：参数热力图、稳定区分析
- Walk-forward 验证结果展示
- Paper-to-Live 准入评估看板：
  - 准入记录列表（admission_id、策略、状态、readiness_score）
  - Paper 指标详情
  - 准入评估结果（通过/未通过各项检查）

交互：

- 发起新回测（选择策略、参数、标的、时间范围）
- 发起参数扫描（sweep）
- 查看回测详情和交易明细
- 创建 Paper-to-Live 准入申请
- 提交准入审批

数据来源：

- `POST /backtest/run` 发起回测
- `POST /backtest/run-sweep` 参数扫描
- `GET /backtest/` 回测列表
- `GET /backtest/{backtest_id}` 回测详情
- `POST /validation/admission` 创建准入
- `POST /validation/admission/{id}/metrics` 收集指标
- `POST /validation/admission/{id}/evaluate` 评估
- `POST /validation/admission/{id}/approve` 审批

### FR-UI-008 审计与合规面板（Audit）

展示内容：

- 审计事件时间线：按时间倒序展示所有审计事件
- 查询过滤：按实体类型（signal / order / position / strategy / agent_task 等）、实体ID、关联ID（correlation_id）、时间范围、告警等级过滤
- 实体审计追踪：选择任一实体，展示从信号生成到最终成交的完整链路
- Agent 操作审计：展示 Agent 任务、工具调用、Proposal、审批记录

交互：

- 点击审计事件查看详情
- 按实体ID追踪完整操作链
- 导出审计日志

数据来源：

- `GET /audit/events` 审计事件列表
- `GET /audit/trace/{entity_type}/{entity_id}` 实体审计追踪

### FR-UI-009 系统监控面板（Monitoring）

展示内容：

- 系统健康仪表盘：
  - QMT 延迟（ms）、连接状态
  - 数据延迟（ms）、Bar 聚合状态
  - CPU / 内存使用率
  - Kill Switch 状态
- 告警列表：按 P0 / P1 / P2 / P3 分级展示，未确认告警置顶
- Agent 任务监控：任务积压数、超时数、失败率、活跃任务列表
- 指标趋势图：订单成功率、成交率、策略错误率的时间序列

交互：

- 确认/处理告警
- 查看告警详情和关联事件
- 时间范围选择（1h / 6h / 24h / 7d）

数据来源：

- `GET /health` 系统健康
- `GET /risk/status` 风控状态
- 监控指标（MetricsCollector）
- 告警数据（AlertService）

### FR-UI-010 告警与通知（Alerts）

展示内容：

- 实时告警推送（WebSocket）
- 告警列表：等级、内容、触发时间、确认状态
- 告警规则配置：查看当前告警阈值和触发条件

交互：

- 告警确认与处理
- 通知渠道管理（邮件、钉钉、企业微信等）
- 告警规则修改（需审批）

数据来源：

- WebSocket 实时推送
- 告警服务（AlertService + NotificationRouter）

## 30.5 AI 对话界面功能需求

### FR-CHAT-001 对话界面

- 侧边栏或独立页面的对话窗口，可拖拽调整大小
- 支持 Markdown 渲染（表格、代码块、图表内嵌）
- 对话历史保存与回溯（按会话分组）
- 多轮对话上下文保持
- 对话中可插入图表（收益曲线、持仓饼图等）

### FR-CHAT-002 Agent 交互

用户自然语言输入的完整处理链路：

> 用户输入 → Hermes Agent 解析意图 → 调用受控工具（白名单） → 返回结构化结果 → 渲染给用户

展示内容：

- Agent 操作可视化：显示当前正在调用的工具名称、等待状态
- Agent 治理链可视化：Task → Proposal → Policy Check → Approval → Execution 各阶段状态
- Agent 角色标识：当前对话由哪个角色处理（Research / Monitoring / Recovery / Audit 等）
- 工具调用结果展示：表格、图表、摘要文本

### FR-CHAT-003 Dashboard 联动

- 对话中提及的实体（持仓、订单、策略、标的）可点击跳转到对应 Dashboard 页面
- Dashboard 页面可通过右键菜单或按钮唤起 AI 对话，自动带入当前页面上下文（如"分析这个订单为什么被拒绝"）
- AI 生成的图表可嵌入对话流，也可展开到 Dashboard 全屏查看

### FR-CHAT-004 审批流集成

- Agent Proposal 在对话中以卡片形式展示，包含：建议内容、置信度、影响范围
- 用户可直接在对话中点击"审批通过"或"拒绝"，附带审批意见
- 审批操作需二次确认弹窗
- 审批结果实时反映到 Dashboard（策略状态变更、订单状态变更等）

### FR-CHAT-005 快捷指令

- 支持斜杠命令：`/backtest`、`/flatten`、`/approve`、`/status`、`/audit` 等
- 常用操作一键触发（如"查看当前持仓"、"最近回测结果"）
- 指令自动补全（输入 `/` 后弹出可用命令列表，**列表根据用户角色过滤，未授权命令不显示**）
- 命令参数提示
- 斜杠命令强制角色检查：`/flatten`、`/approve` 等敏感命令仅限拥有对应权限的角色执行，未授权用户直接输入时返回 403 提示

### FR-CHAT-006 多模型支持

- 支持接入 Claude API / OpenAI API / 本地模型（如 Ollama）
- 模型选择由平台管理员统一配置，非用户自行选择（避免未授权模型接入）
- 不同会话可使用不同模型（在管理员配置的范围内）
- 模型选择不影响后端 Agent 治理链（治理链由 Hermes Agent 内部的 Policy Engine 实现，与前端选择的 LLM 无关）
- 流式输出支持（Server-Sent Events）

数据安全约束：

- Live 环境的 Chat 会话仅允许使用本地模型（Ollama）或经安全审查的私有部署模型，禁止将持仓、订单、账户等实盘数据发送到第三方 API（Claude/OpenAI）
- **Live 环境本地模型不可用时的降级策略：** 禁止回退到第三方云模型。显示明确的错误提示："当前本地模型不可用，请检查 Ollama 服务状态。实盘数据不允许发送到外部服务。" 提供重试按钮和管理员通知。不缓存任何实盘数据在降级状态。
- Research / Backtest 环境可使用第三方模型，但发送前必须脱敏处理（移除真实账户 ID、具体金额等敏感信息）
- 模型选择变更需审计（FR-NFR-006）
- 所有 LLM 调用的 prompt 和响应必须记录在审计存储中（保留 90 天）

### FR-CHAT-007 Agent 能力范围

对话界面的 Agent 可以（与 PRD 7.2 L1-L3 层对应）：

- 查询行情、持仓、订单、账户状态（L1 只读分析）
- 发起回测、验证、对账任务（L3 受控触发）
- 生成研究报告、策略建议（L2 受限建议）
- 解释风控拦截原因（L1 只读分析）
- 提供恢复建议（L2 受限建议）
- 生成审计报告（L1 只读分析）

对话界面的 Agent 不可以（与 PRD 7.2 L4 禁止层对应）：

- 直接下单、撤单
- 绕过审批修改实盘配置
- 修改风控阈值
- 直接调用 QMT 接口
- 直接写入核心交易状态

## 30.6 实时数据需求

### FR-REALTIME-001 WebSocket 推送

后端需新增 WebSocket 端点（`/ws`），推送以下实时数据：

- 持仓变动（价格更新、数量变动）
- 订单状态变更（提交、部分成交、成交、拒绝、撤销）
- 信号生成（新信号实时推送）
- 风控状态变更（规则触发、Kill Switch 变化）
- 告警触发（P0-P3 级别告警）
- Agent 任务状态变更（任务开始、完成、失败）

认证：

- WebSocket 通过 `Sec-WebSocket-Protocol` 头传递 Bearer Token（禁止通过 query parameter 传递，避免 token 泄露到服务器日志）
- 服务端在握手时验证 token，验证失败拒绝连接
- 连接期间 token 过期，服务端发送 `{"type": "force_disconnect", "reason": "token_expired"}` 后主动断开
- WebSocket 是只读推送通道，客户端不能通过 WebSocket 发送操作命令，所有写操作走 REST API

消息格式：

```json
{
  "type": "order_update",
  "data": { ... },
  "event_id": "evt_abc123",
  "sequence": 1001,
  "timestamp": "2025-01-15T10:30:00+08:00"
}
```

每条消息包含 `event_id`（PipelineBus Redis Stream entry ID）和 `sequence`（per-user 单调递增序列号），用于前端去重和排序。

消息推送角色过滤：

| 事件类型 | 量化研究者 | 交易执行者 | 系统管理者 |
|---------|-----------|-----------|-----------|
| position_update | 仅 Paper/Backtest | 本账户 Live + Paper | 全部 |
| order_update | 仅 Paper/Backtest | 本账户 Live + Paper | 全部 |
| signal_new | 本策略 | 本策略 | 全部 |
| risk_change | 无 | 本账户 | 全部 |
| alert | P2-P3 | P1-P3 | 全部 |
| agent_task_update | 本用户创建的 | 本用户创建的 | 全部 |

重连与消息恢复：

- 客户端断线后使用指数退避重连（最大 30s）
- 重连时发送 `{"type": "reconnect", "last_sequence": 1000}`
- 服务端补发 last_sequence 之后的所有未确认消息（服务端保留最近 100 条 per-user 推送，TTL 5min）
- 若缺失消息超出保留范围，服务端发送完整状态快照
- 客户端按 sequence 单调递增处理消息，乱序消息丢弃

REST / WebSocket 排序：

- REST API 响应包含 `last_sequence` 字段
- 前端拒绝 sequence <= 已处理最大值的状态更新
- 写操作（POST/PUT）后 500ms 内以 REST 响应状态为准

心跳：

- 双向应用层心跳：客户端每 30s 发送 `{"type": "ping"}`，服务端回复 `{"type": "pong"}`
- 服务端 60s 未收到 ping → 主动断开
- 客户端 60s 未收到 pong → 触发重连
- 不使用 WebSocket 协议层 ping/pong（代理可能不透传）

### FR-REALTIME-002 数据刷新策略

- **实盘环境（Live）**：WebSocket 实时推送，无需手动刷新
- **仿真环境（Paper）**：WebSocket 实时推送
- **回测/研究环境（Backtest / Research）**：手动刷新或短间隔轮询
- **Dashboard 支持"自动刷新"开关**，可全局切换
- **WebSocket 断线时自动降级**为 REST 轮询（30s 间隔），并显示"数据可能陈旧"警告
- **安全关键操作**（Kill Switch、Force Flatten）始终通过 REST POST 发送，不依赖 WebSocket。REST 端点同步返回操作 ID，即使 WebSocket 断线也能确认操作已执行

### FR-REALTIME-003 Kill Switch / Force Flatten 断线保障

- Kill Switch 和 Force Flatten 通过 REST `POST` 触发，返回同步确认（操作 ID + 状态）
- WebSocket 仅用于状态通知，不用于操作触发
- WebSocket 断线时，Dashboard 顶部显示持续警告横幅"实时数据连接中断，操作仍可用但状态更新可能延迟"
- Force Flatten 进度在 WebSocket 不可用时通过 `GET /risk/flatten/{flatten_id}` REST 轮询获取
- 用户触发 Kill Switch 后 UI 显示"操作已提交"等待 REST 响应，而非假设成功

## 30.7 非功能需求

### FR-NFR-001 响应时间

- Dashboard 页面首次加载 < 2s
- Dashboard 页面切换 < 500ms
- WebSocket 关键事件延迟（Kill Switch、订单成交） < 200ms（P99）
- WebSocket 信息事件延迟（持仓价格更新） < 500ms（P99）
- AI 对话首字响应 < 3s（流式输出开始时间）
- REST API 请求响应 < 1s（90th percentile）

### FR-NFR-002 数据安全

- 前端不存储敏感凭证（API Key、数据库密码等）
- API 认证使用 Bearer Token（JWT），通过 `/auth/login` 获取
- API 通信使用 HTTPS
- WebSocket 使用 WSS，认证通过 `Sec-WebSocket-Protocol` 头传递（禁止 query parameter）
- SSE 认证使用 Bearer Token（Authorization 头），浏览器原生 EventSource 不支持自定义头时使用 fetch + ReadableStream 实现
- 实盘操作（Kill Switch、Force Flatten、策略启停）需二次确认
- CSRF 保护：SameSite Cookie + CSRF Token（REST 端点）；SSE/WebSocket 使用 Bearer Token 不受 CSRF 影响
- XSS 防护：对话内容严格转义，Markdown 渲染禁用 raw HTML，图片 src 仅允许 http/https 协议（禁止 data: URI），链接 href 仅允许 http/https/mailto（禁止 javascript:），渲染前通过 DOMPurify 清洗
- 审批卡片必须来自服务端结构化数据，LLM 不得生成审批按钮

### FR-NFR-003 可访问性

- 支持中文界面（主要用户语言）
- 支持暗色/亮色主题切换（所有标准 UI 组件和图表必须正确渲染两种主题，偏好设置持久保存在 localStorage）
- 响应式布局：桌面端优先，平板端可用（V1.5 不包含移动端适配）
- 关键数据使用颜色 + 图标双重标识（不依赖单一颜色传达信息）
- Live 环境视角使用醒目视觉标识（顶部红色横幅）

### FR-NFR-004 会话管理

- 会话超时：活跃 30 分钟（有 API 调用自动续期），不活跃 5 分钟
- Live 环境敏感操作后强制重新认证
- 单用户最多 3 个并发登录会话（每个会话可建立 1 个 WebSocket 连接，即最多 3 个 WebSocket 连接）
- 服务端支持即时令牌失效（管理员撤销权限时立即断开所有连接）
- WebSocket 连接与会话生命周期绑定，会话失效时服务端主动断开 WebSocket

### FR-NFR-005 速率限制

- REST API 只读端点：100 req/min per user
- REST API 交易操作（下单、撤单）：10 req/min per user
- **紧急操作（独立限流桶，不受交易限流影响）：**
  - Kill Switch 激活：1 req/min per user（激活后 60s 冷却期，防止误触连击）
  - Kill Switch 停用：1 req/5min per user（需审批，低频操作）
  - Force Flatten：3 req/min per user
- REST API 回测启动：5 req/min per user
- Chat 消息：20 msg/min per user，60 msg/hour per session
- WebSocket 客户端消息：10 msg/min per connection（超出断连）
- SSE 活跃流：3 per user
- 所有超限返回 429 Too Many Requests 或 force_disconnect

### FR-NFR-006 UI 操作审计

以下 UI 操作必须生成审计事件，与核心审计系统（FR-UI-008）使用同一 `audit/events` 端点：

- Kill Switch 激活 / Force Flatten 触发
- 手动撤单
- 策略状态转换
- 审批决策（批准/拒绝）
- AI Chat 命令和响应
- 环境视角切换
- 告警确认
- 会话登录/登出

审计事件字段：用户 ID、角色、会话 ID、IP 地址、时间戳、操作类型、目标实体、变更前后状态。

### FR-NFR-007 错误处理

- P0/P1 级别 API 错误：弹窗提示，显示后端错误原因，提供重试选项
- P2/P3 级别 API 错误：Toast 提示
- Kill Switch / Force Flatten 被后端拒绝：显示具体拒绝原因（如"当前无持仓可平"）
- 会话过期（401）：重定向登录页，保留表单数据
- AI Chat 错误：在对话流中显示错误标记，提供重试按钮
- 网络不可用：显示连接状态横幅，缓存最后已知数据
- 并发冲突：若实体在操作前被其他用户修改，返回 409 Conflict，提示"数据已变更，请刷新后重试"

## 30.8 版本规划

### V1.5（与 PRD V1.5 对齐）

交付重点：

- Dashboard 核心面板：总览面板（FR-UI-001）+ 持仓管理（FR-UI-002）+ 订单管理（FR-UI-003）+ 风控监控（FR-UI-004）
- 策略管理面板基础版（FR-UI-005）：列表 + 状态查看
- AI 对话基础功能（FR-CHAT-001 / 002 / 007）：查询类操作、Agent 可视化
- 审批流界面（FR-CHAT-004）：Proposal 查看 + 审批操作
- WebSocket 实时推送（FR-REALTIME-001）
- 快捷指令（FR-CHAT-005）

### V2.0（与 PRD V2.0 对齐）

交付重点：

- 信号监控面板（FR-UI-006）
- 回测与验证可视化增强（FR-UI-007）：收益曲线、热力图、参数分析
- Paper-to-Live 准入看板完整版
- Agent 治理链完整可视化
- 审计与合规面板（FR-UI-008）
- 系统监控面板（FR-UI-009）
- 告警与通知（FR-UI-010）
- Dashboard 联动（FR-CHAT-003）
- 多模型支持（FR-CHAT-006）
- 移动端适配