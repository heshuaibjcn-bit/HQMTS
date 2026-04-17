# 

**项目名称**：Hermes Quant Minute Trading System  
**简称**：HQMTS  
**文档版本**：SAD V1.3 Outline  
**对应 PRD**：PRD V1.3  
**前序版本**：SAD V1.2  
**适用市场**：A股  
**交易周期**：5m / 15m / 30m / 60m  
**历史数据源**：Tushare Pro  
**实盘接口**：QMT  
**智能编排层**：Hermes Agent  
**文档状态**：架构设计大纲 / V1.3 修订建议版

---

# 0. V1.3 修订定位

SAD V1.3 在 SAD V1.2 基础上不推翻既有架构，而是根据 PRD V1.3 的核心变化进行收敛和补强。

V1.3 的关键修订方向是：

1. 明确 **Hermes Agent 是受控智能编排层，不是交易确定性内核**
2. 强化 **确定性交易内核** 的中心地位
3. 明确 Agent 只能通过 **白名单 Tool / Control API / Transition API** 间接作用系统
4. 增加 **AgentTask / AgentProposal / ToolInvocation / ApprovalRequest** 等治理对象
5. 建立 **Proposal → Policy Check → Approval → Controlled Execution → Audit** 闭环
6. 明确 Agent 的失败语义、幂等要求、超时策略和 fail-closed 原则
7. 强化 Live 主路径与 Agent 的隔离
8. 将 Agent 审计、权限、资源隔离提升为实施级架构约束

SAD V1.3 的目标不是增加更多智能功能，而是把：

> **Agent 可以做什么、不能做什么、如何做、失败如何处理、如何审计**

写成可实施、可测试、可验收的架构基线。

---

# 1. 文档目的

本文档用于定义 HQMTS V1.3 的系统架构设计大纲，作为后续详细设计文档、DDL、API、状态机、事件流、测试计划和上线验收的基线。

本文档重点指导：

- 系统逻辑分层
- Live 确定性交易内核设计
- 数据与事件架构设计
- QMT 执行网关设计
- 风控与资金预占设计
- 状态机与恢复机制设计
- Hermes Agent 接入架构设计
- Agent Tool 权限模型设计
- Agent Proposal / Approval 闭环设计
- 审计与版本治理设计
- 故障降级和验收测试设计

本文档中的“必须”“禁止”“默认”具有架构约束效力。  
若后续实现需偏离，必须通过架构评审和变更审批。

---

# 2. 架构目标

## 2.1 业务目标

系统支持：

1. A股分钟级多周期策略研究与交易
2. 回测、Paper、Live 全流程闭环
3. 多策略并行运行
4. QMT 实盘执行
5. Hermes Agent 辅助研究、验证、监控、报告、对账和恢复建议
6. 研究结果、Agent 行为、实盘行为均可审计、可复现、可追溯

---

## 2.2 实盘目标

Live 架构必须满足：

1. 订单、成交、持仓、账户状态可恢复
2. 重复事件不导致重复下单
3. 乱序回报不导致非法状态
4. 多策略共享账户不会超额承诺可用资金
5. 人工干预可被识别、对账、审计、降级
6. 关键依赖故障时可进入明确降级模式
7. 恢复后默认保守，不自动冒进恢复交易
8. Agent 不得绕过交易主路径、风控和审批
9. Live 主路径不得依赖 Agent 推理结果才能继续安全运行

---

## 2.3 Agent 接入目标

Hermes Agent 接入必须满足：

1. Agent 仅作为受控智能编排层和辅助决策层
2. Agent 不直接调用 QMT 下单/撤单接口
3. Agent 不直接写核心交易状态表
4. Agent 不替代风控引擎做最终 allow/reject 裁决
5. Agent 所有有副作用动作必须通过白名单工具触发
6. Agent 所有工具调用必须可审计
7. Agent 所有 Live 相关 Proposal 必须经过 Policy Check
8. 需要人工审批的 Proposal 必须进入 Approval 流程
9. Agent 超时、失败、上下文缺失时默认 fail-closed

---

## 2.4 实施目标

SAD V1.3 要达到：

1. 可直接指导 DDL 设计
2. 可直接导出状态机文档
3. 可直接导出 API / Tool 权限清单
4. 可直接导出事件 Topic / Stream 设计
5. 可直接导出 Agent 审计和越权测试矩阵
6. 可支持多人并行开发而不产生核心歧义

---

# 3. 架构原则

## 3.1 研究灵活，实盘保守

研究允许快速试错；实盘必须可解释、可恢复、可审计。

---

## 3.2 确定性内核优先

所有直接影响实盘资产、订单、成交、持仓、账户和风险暴露的关键路径，必须由确定性服务、显式状态机和可审计事务承载。

Agent 不能成为交易确定性内核的一部分。

---

## 3.3 统一接口，不强行统一底层行为

统一对象：

- Strategy
- Signal
- ExecutionIntent
- RiskCheckResult
- CashReservation
- OrderRequest
- Order
- Trade
- Position
- Account
- DecisionSnapshot
- VersionBinding
- AgentTask
- AgentProposal
- ToolInvocation
- ApprovalRequest

允许差异：

- 数据来源
- 撮合器
- 执行器
- 延迟模型
- 故障来源
- 状态权威源
- Agent 工作流实现

---

## 3.4 状态优先于流程

设计任何流程前，先定义：

- 状态对象
- 状态权威源
- 合法迁移
- 幂等键
- 串行化单位
- 审计落点

---

## 3.5 事件至少一次，业务幂等

系统不承诺全局 exactly-once。  
关键保障来自：

- 幂等键
- 数据库唯一约束
- 串行化消费
- 状态机合法迁移
- 恢复对账
- ToolInvocation 去重
- AgentTask correlation_id

---

## 3.6 最后一跳必须可控

真实下单前必须经过不可绕过的 Final Pre-Submit Check。

该检查不得被：

- 策略
- Agent
- 配置
- 运维脚本
- 外部 API

绕过。

---

## 3.7 外部系统不可信

QMT、网络、回报顺序、数据库、缓存、Agent 输出、LLM 推理结果都必须假设可能异常。

---

## 3.8 Agent 受控工具原则

Agent 不直接作用生产核心对象。  
Agent 只能通过：

- Read Tool
- Task Tool
- Controlled Operation Tool
- Proposal API
- Approval API

间接作用系统。

---

## 3.9 Live 默认失败关闭原则

Live 相关 Agent 任务出现以下情况时，默认不得继续推进高风险动作：

- 超时
- 输出不完整
- Tool 调用失败
- 上下文缺失
- Policy Check 不通过
- Approval 状态不明确
- 审计写入失败

---

# 4. 系统总体架构

## 4.1 逻辑分层

V1.3 系统分为 10 层：

1. 外部接入层
2. 数据处理层
3. 特征与研究层
4. 策略运行时层
5. Backtest / Paper / Live 引擎层
6. 风控与执行层
7. 确定性交易内核层
8. Hermes Agent 智能编排层
9. 治理与审计层
10. 存储与可观测层

---

## 4.2 推荐逻辑架构图

Text

                  ┌─────────────────────────────┐

                  │        Hermes Agent Layer     │

                  │ Research / Analysis / Report  │

                  │ Reconciliation / Recovery     │

                  └──────────────┬──────────────┘

                                 │

                    Tool / Proposal / Approval API

                                 │

                  ┌──────────────▼──────────────┐

                  │     Governance & Control      │

                  │ Policy / Approval / Audit     │

                  └──────────────┬──────────────┘

                                 │

        ┌────────────────────────▼────────────────────────┐

        │             Deterministic Trading Core            │

        │ Strategy Runtime / Risk / Reservation / Execution │

        │ Order FSM / Trade Ledger / Reconciliation         │

        └──────────────┬─────────────────────┬────────────┘

                       │                     │

              ┌────────▼────────┐    ┌──────▼────────┐

              │   Data Layer     │    │   QMT Adapter │

              │ Tushare / Bars   │    │ Market/Trade  │

              └─────────────────┘    └───────────────┘

---

## 4.3 Live 最小可信链路

Live 同步关键路径保留以下组件：

1. QMT Adapter
2. Real-time Bar Builder
3. Strategy Runtime
4. DecisionSnapshot Builder
5. Risk Service
6. Reservation Manager
7. Target-to-Order Service
8. Execution Service
9. Final Pre-Submit Check
10. Local State Cache
11. Live Operational DB
12. Emergency Controller
13. Audit Writer

其余均视为异步外围。

---

## 4.4 Agent 与 Live 主路径隔离

Live 主路径为：

Text

Completed Bar

→ DecisionSnapshot

→ Strategy Runtime

→ Signal

→ RiskCheckResult

→ CashReservation

→ ExecutionIntent

→ Final Pre-Submit Check

→ OrderRequest

→ QMT Submit

→ Order / Trade Update

→ Position / Account Reconciliation

架构约束：

1. Agent 不得插入该主路径作为必要同步依赖
2. Agent 不得生成可直接提交 QMT 的 OrderRequest
3. Agent 不得修改主路径对象的最终状态
4. Agent 可生成建议、报告、解释、恢复方案，但必须通过 Proposal / Approval / Controlled Execution 闭环生效

---

# 5. 环境与部署隔离

## 5.1 环境定义

|环境|作用|是否真实下单|Agent 权限|
|---|---|---|---|
|Research|数据研究、因子探索、策略候选生成|否|可执行研究编排|
|Backtest|历史回测|否|可发起回测与分析|
|Paper|实时仿真|否|可发起仿真、分析、报告|
|Live|实盘交易|是|只读分析、受控触发、Proposal|

---

## 5.2 节点职责

### Research / Backtest Node

允许：

- 历史数据抓取
- 批量计算
- 回测
- Agent 研究任务
- 策略候选生成

禁止：

- 持有 QMT 下单凭证
- 访问 Live 运行写权限
- 直接修改 Live 配置
- 直接创建 Live 生效对象

---

### Control / Paper Node

允许：

- 编排调度
- 审批
- Paper 运行
- 聚合监控
- Agent 分析和报告

禁止：

- 绕过审批直接启用 Live
- 直接向 QMT 下单
- 直接修改 Live 核心状态

---

### Live / QMT Node

允许：

- 实时策略运行
- 风控
- 资金预占
- 下单
- 对账
- 故障降级
- 最小必要只读 Agent 查询

禁止：

- 重型研究任务
- 非白名单 Agent 自由执行
- 大规模分析查询
- 未审批配置热更
- Agent 直接执行下单/撤单

---

## 5.3 Agent 运行隔离

Agent Runtime 应与 Live QMT Node 隔离部署。

默认部署要求：

1. Agent Runtime 不持有 QMT 交易凭证
2. Agent Runtime 不持有 Live DB 直接写权限
3. Agent Runtime 通过 Tool Gateway 访问系统能力
4. Tool Gateway 执行权限校验、policy check 和审计
5. Live 交易时段限制 Agent 大查询和重型任务

---

# 6. 存储与依赖分级

## 6.1 存储分类

|存储|用途|是否 Live 关键依赖|
|---|---|---|
|Live Operational DB|实盘状态与审计|是|
|Research Analytics Store|历史研究|否|
|Agent State Store|AgentTask、Proposal、ToolInvocation|中|
|Redis / Stream|缓存与事件辅助|弱到中等|
|Object Storage|报告与归档|否|
|Log Storage|日志检索|否|
|Approval Store|审批记录|中到高|

---

## 6.2 Live Operational DB 设计原则

必须满足：

1. 订单、成交、持仓快照、账户快照、预占资金、执行日志可持久化
2. 唯一约束可支撑幂等
3. 故障时可触发明确降级策略
4. 不与研究查询争抢主资源
5. 不允许 Agent 直接写核心交易表

---

## 6.3 Agent State Store 原则

Agent State Store 用于保存：

- AgentTask
- AgentProposal
- ToolInvocation
- Agent workflow version
- Agent 输出报告引用
- Agent 失败与重试记录

约束：

1. Agent State Store 不得作为交易事实账本
2. Agent memory 不得替代数据库事实状态
3. Agent 输出必须通过受控对象引用交易事实，不得自行维护影子账本

---

## 6.4 Redis 原则

Redis 允许用于：

- 事件分发
- 最近行情缓存
- 幂等辅助缓存
- 非权威热点数据
- Agent 任务队列辅助

Redis 禁止用于：

- Order 最终权威状态
- Trade 最终权威状态
- Position / Account 最终权威状态
- 审计唯一落点
- Approval 唯一状态源

---

# 7. 领域模型

## 7.1 核心交易对象

1. Instrument
2. Bar
3. FeatureSnapshot
4. DecisionSnapshot
5. Strategy
6. StrategyInstance
7. Signal
8. RiskCheckResult
9. CashReservation
10. ExecutionIntent
11. OrderRequest
12. Order
13. Trade
14. Position
15. Account
16. ReconciliationResult
17. RecoverySession
18. VersionBinding
19. ExternalManualEvent

---

## 7.2 治理与 Agent 对象

V1.3 新增或强化以下对象：

1. AgentTask
2. AgentProposal
3. ToolInvocation
4. ApprovalRequest
5. PolicyCheckResult
6. ControlledExecution
7. AuditEvent
8. CorrectionEvent

---

## 7.3 DecisionSnapshot

定义某次策略决策看到的完整输入快照。

字段建议：

- decision_snapshot_id
- strategy_instance_id
- decision_time
- cycle
- feature_snapshot_id
- bar_set_id
- snapshot_completeness
- universe_scope
- data_version
- feature_version
- created_at

约束：

1. Live 正式 Signal 必须绑定 DecisionSnapshot
2. 缺失 DecisionSnapshot 的 Signal 不得进入 Live 下单链路
3. DecisionSnapshot 不得由 Agent 伪造或补写为正式决策依据

---

## 7.4 CashReservation

定义多策略共享账户下，对可用资金的预占。

字段建议：

- reservation_id
- account_id
- strategy_instance_id
- signal_id / execution_intent_id
- reserved_amount
- currency
- status
- expires_at
- released_reason
- created_at
- updated_at

状态：

- active
- partially_consumed
- fully_consumed
- released
- expired
- invalid

---

## 7.5 ExternalManualEvent

定义系统外源人工或未知交易动作。

字段建议：

- external_event_id
- account_id
- event_type
- broker_order_id / broker_trade_id
- instrument_id
- side
- quantity
- price
- detected_at
- source_confidence
- linked_internal_order_id nullable
- action_taken
- audit_note

---

## 7.6 AgentTask

表示 Hermes Agent 发起的一次任务。

字段建议：

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

状态建议：

- created
- planning
- running
- waiting_tool
- completed
- failed
- timeout
- canceled
- escalated

约束：

1. 每次 Agent 任务必须有唯一 ID
2. 每次 Agent 任务必须记录环境
3. Live 相关任务必须绑定 workflow_version
4. AgentTask 不等于生产执行动作

---

## 7.7 AgentProposal

表示 Agent 输出的建议。

字段建议：

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

状态建议：

- drafted
- policy_checking
- policy_rejected
- pending_approval
- approved
- rejected
- execution_pending
- executed
- execution_failed
- expired
- canceled

约束：

1. Proposal 不是最终执行动作
2. Proposal 必须经过 Policy Check
3. Live 高风险 Proposal 必须经过 Approval
4. Proposal 过期后不得执行

---

## 7.8 ToolInvocation

表示一次 Agent 工具调用。

字段建议：

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
- policy_check_id
- correlation_id

side_effect_level：

- none
- read_only
- task_trigger
- controlled_operation
- forbidden_attempt

约束：

1. 所有 Tool 调用必须审计
2. 有副作用 Tool 必须有幂等键
3. Live 相关 Tool 必须经过权限与 policy 校验
4. forbidden_attempt 必须告警并留痕

---

## 7.9 ApprovalRequest

表示需要人工审批的请求。

字段建议：

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
- approval_snapshot_ref

状态建议：

- pending
- approved
- rejected
- expired
- canceled

---

## 7.10 ControlledExecution

表示经过 Proposal / Approval 后由确定性服务执行的受控动作。

字段建议：

- controlled_execution_id
- source_proposal_id
- approval_request_id nullable
- action_type
- target_object_type
- target_object_id
- execution_status
- executed_by_service
- started_at
- completed_at
- result_ref
- failure_reason

约束：

1. ControlledExecution 必须由确定性服务执行
2. 不得由 Agent Runtime 直接写核心状态完成执行
3. 执行结果必须进入 AuditEvent

---

# 8. 状态权威模型

## 8.1 权威源定义

|对象|正常权威源|恢复/对账权威源|本地用途|
|---|---|---|---|
|Order|QMT回报 + 本地订单状态机|QMT委托查询优先|生命周期管理|
|Trade|QMT成交回报|QMT成交查询优先|持仓账本更新|
|Position|QMT持仓查询优先|QMT持仓查询绝对优先|策略上下文、风控|
|Account|QMT账户查询优先|QMT账户查询绝对优先|可用资金、风险控制|
|Signal|本地策略运行时|本地数据库|审计与追踪|
|CashReservation|本地 Reservation Manager|本地数据库|资金仲裁|
|ExecutionIntent|本地 Execution Service|本地数据库|执行中间态|
|FeatureSnapshot|本地特征服务|本地数据版本|决策输入|
|DecisionSnapshot|本地决策构建器|本地数据库|决策一致性|
|AgentTask|Agent State Store|Agent State Store|Agent任务追踪|
|AgentProposal|Governance Store|Governance Store|建议与审批流|
|ApprovalRequest|Approval Store|Approval Store|人工审批|
|ControlledExecution|确定性执行服务|Operational DB|受控动作落地|

---

## 8.2 权威模式

系统定义三种权威模式：

1. `event_primary`
2. `query_primary`
3. `degraded`

### event_primary

- 实时回报为主
- 查询用于定时校验

### query_primary

- 回报流异常时启用
- 周期查询结果优先
- 实时回报视为补充信息

### degraded

- 外部状态不稳定
- 仅允许保守动作
- 禁止新开仓，必要时仅平仓或暂停

---

## 8.3 Agent 不作为权威源

Agent 输出不得作为以下对象的权威源：

- Account
- Position
- Order
- Trade
- CashReservation
- RiskCheckResult
- StrategyInstance 状态
- Live 配置
- 风控阈值

Agent 只能输出：

- 分析
- 建议
- Proposal
- 报告
- 恢复步骤建议

---

# 9. 时间基准与时钟同步规范

## 9.1 时间基准

系统统一原则：

- 业务展示使用 `Asia/Shanghai`
- 存储建议使用 UTC + 时区字段，或统一存本地时区但必须一致
- 所有服务必须统一时区策略，不允许混用

---

## 9.2 关键时间字段定义

|字段|含义|来源|
|---|---|---|
|market_time|交易日市场时间|交易日历|
|bar_end_time|Bar 完成时间|Bar Builder|
|decision_time|策略做出决策时间|Strategy Runtime|
|signal_created_at|Signal 持久化时间|系统本地时间|
|submit_attempt_time|调用 QMT 前时间|Execution Service|
|broker_accept_time|券商接受时间|QMT回报/查询|
|trade_time|成交时间|QMT成交回报/查询|
|snapshot_time|账户/持仓快照时间|查询时刻|
|agent_task_started_at|Agent 任务开始时间|Agent Runtime|
|tool_invoked_at|Tool 调用开始时间|Tool Gateway|
|approval_decision_at|审批决策时间|Approval Service|

---

## 9.3 时钟同步要求

- Live 节点必须启用时间同步
- 时间偏移超阈值触发告警
- 偏移严重时进入 `pause_open`
- Agent Runtime 与 Tool Gateway 也必须记录统一时间基准
- 审批、Tool 调用、ControlledExecution 必须能按时间线重建

---

# 10. 数据与特征架构

## 10.1 数据分层

1. raw
2. standardized
3. aggregated
4. feature
5. result
6. agent_report

---

## 10.2 数据质量等级

|等级|含义|使用规则|
|---|---|---|
|PASS|校验通过|全环境可用|
|WARN|非致命问题|Research/Backtest 可配置，Paper/Live 需显式允许|
|FAIL|致命异常|禁止正式使用|
|UNKNOWN|未校验|禁止正式使用|

---

## 10.3 价格口径

|层级|价格口径|
|---|---|
|原始行情层|不复权|
|撮合/执行层|不复权|
|实盘层|不复权|
|特征层|可配置复权口径，但必须记录|
|信号层|不得直接把复权价格当下单价|
|Agent 报告层|必须标注价格口径|

---

## 10.4 Agent 数据访问约束

Agent 访问数据必须遵守：

1. 最小上下文原则
2. 环境隔离原则
3. 脱敏原则
4. 不得读取非必要 Live 敏感信息
5. 不得对 Live DB 发起大范围分析查询
6. Agent 报告必须引用数据版本和查询时间

---

# 11. 决策快照一致性模型

## 11.1 决策一致性原则

任意一个正式 Signal 必须绑定一个可重建的 DecisionSnapshot。  
DecisionSnapshot 必须明确该次决策所看到的：

- Bar 集
- FeatureSnapshot
- 数据版本
- 特征版本
- universe 范围
- 快照完整性状态

---

## 11.2 FeatureSnapshot 与 Signal 绑定

正式 Signal 必须携带：

- feature_snapshot_id
- decision_snapshot_id
- bar_set_id
- decision_time

若任一缺失，正式 Signal 不得进入 Live 下单链路。

---

## 11.3 Snapshot 完整性

`snapshot_completeness` 枚举：

- complete
- partial_allowed
- partial_blocked
- invalid

解释：

- `complete`：所需输入全部到齐
- `partial_allowed`：允许部分输入缺失但策略已声明可运行
- `partial_blocked`：输入未齐，不允许决策
- `invalid`：输入错误或污染

---

## 11.4 横截面策略规则

如果策略依赖横截面特征，必须声明：

- universe_scope
- snapshot_completion_rule
- max_wait_ms / max_wait_s
- partial_universe_policy

`partial_universe_policy` 可选：

1. delay
2. skip
3. run_with_partial
4. downgrade_to_single_name_logic

默认策略：`delay` 或 `skip`，不默认 `run_with_partial`。

---

## 11.5 Agent 与 DecisionSnapshot 边界

Agent 可以：

- 分析 DecisionSnapshot 完整性
- 解释 Signal 产生原因
- 生成异常报告
- 提出数据修复建议

Agent 不可以：

- 修改已落库 DecisionSnapshot
- 伪造 DecisionSnapshot
- 用自然语言解释替代正式快照
- 让缺失快照的 Signal 进入 Live 链路

---

# 12. Bar 与事件时序规范

## 12.1 主真源

分钟级内部主真源为 1m Bar。

---

## 12.2 Formal Signal 规则

仅允许基于 `completed bar` 生成正式 Signal。

---

## 12.3 多周期排序

1. 先完成低周期 Bar
2. 再聚合高周期 Bar
3. 多周期策略仅可读取最近已完成上级周期 Bar
4. 不允许引用未来 Bar

---

## 12.4 事件语义

系统采用：

Text

at-least-once delivery + consumer idempotency + serialization key

---

## 12.5 串行化单位

|流程|serialization key|
|---|---|
|单策略决策处理|strategy_instance_id|
|共享账户资金预占|account_id|
|单账户下单最终仲裁|account_id|
|单订单状态更新|order_id / broker_order_id|
|单标的同周期 Bar|instrument_id + cycle|
|单策略单标的 Signal|strategy_instance_id + instrument_id|
|Agent 单任务执行|agent_task_id|
|Proposal 状态推进|proposal_id|
|Approval 状态推进|approval_request_id|
|ControlledExecution 执行|controlled_execution_id / target_object_id|

要求：

1. 同一 serialization key 的关键流程必须串行处理
2. 不允许多个 worker 并发修改同一对象关键状态
3. 如使用多进程/多线程，必须通过队列分区、DB锁或 actor 模型保证串行性

---

## 12.6 去重键

|事件|去重键|
|---|---|
|DecisionSnapshotCreated|strategy_instance_id + decision_time + bar_set_id|
|CashReservationCreated|account_id + execution_intent_id|
|ExternalManualEventDetected|account_id + broker_order_id/broker_trade_id + detected_type|
|AgentTaskCreated|agent_role + task_type + correlation_id|
|ToolInvocationRequested|agent_task_id + tool_name + idempotency_key|
|AgentProposalCreated|source_agent_task_id + proposal_type + target_object_id|
|ApprovalRequestCreated|source_type + source_id + approval_type|
|ControlledExecutionRequested|source_proposal_id + action_type + target_object_id|

---

# 13. Strategy Runtime 与沙箱

## 13.1 统一接口

Text

on_init(context)

on_bar(bar, context)

generate_signal(context) -> Signal | None

on_order_update(order, context)

on_trade_update(trade, context)

on_stop(context)

---

## 13.2 禁止事项

策略禁止：

- 直接下单
- 调用 QMT
- 访问未授权数据库
- 发起外部网络请求
- 自建线程
- 写任意文件
- 绕过 DecisionSnapshot
- 使用未完成 Bar 生成正式 Signal
- 直接调用 Agent Runtime 影响交易决策

---

## 13.3 沙箱约束

沙箱应限制：

- CPU 时间
- 内存
- 文件系统访问
- 网络访问
- 非授权模块导入
- 执行超时

---

# 14. Backtest / Paper / Live 差异矩阵

## 14.1 一致性要求

Paper 必须共享：

- Strategy Runtime
- Risk Service
- DecisionSnapshot 构造逻辑
- Target-to-Order 转换逻辑
- 风控规则版本
- 参数版本绑定
- Agent 报告引用机制（如启用）

---

## 14.2 允许差异

允许差异主要在：

- 行情来源
- 撮合器
- 成交产生方式
- 延迟模型
- QMT 外部故障
- 账户/持仓权威源

---

## 14.3 阻塞性差异

以下差异必须作为 Paper → Live 准入阻塞项或高风险提示：

- Paper 与 Live 使用不同特征供给方式
- Paper 未执行 Final Pre-Submit Check 等价逻辑
- Paper 未走资金预占
- Paper 未覆盖对账/恢复演练
- Paper 中 Agent 具有 Live 不允许的权限

---

# 15. 核心状态机约束

## 15.1 Order 状态机

推荐状态：

- created
- submitting
- submitted
- accepted
- partially_filled
- filled
- cancel_pending
- canceled
- rejected
- expired
- uncertain

合法迁移沿用 V1.2：

|当前状态|允许迁移到|
|---|---|
|created|submitting, rejected, expired|
|submitting|submitted, rejected, uncertain|
|submitted|accepted, partially_filled, filled, cancel_pending, rejected, uncertain|
|accepted|partially_filled, filled, cancel_pending, canceled, rejected, uncertain|
|partially_filled|partially_filled, filled, cancel_pending, canceled, uncertain|
|cancel_pending|canceled, partially_filled, filled, uncertain|
|rejected|终态|
|filled|终态|
|canceled|终态|
|expired|终态|
|uncertain|accepted, partially_filled, filled, canceled, rejected, expired|

约束：

1. `uncertain` 为恢复或乱序修正的过渡态
2. 非法迁移必须被拒绝并记录审计
3. 查询结果可触发 correction 迁移，但必须留痕
4. Agent 不得直接触发 Order 状态迁移

---

## 15.2 Trade 幂等规则

- Trade 以 `broker_trade_id` 为幂等主键
- 同一 `broker_trade_id` 重复到达必须忽略重复写入
- Trade 一经确认，不允许修改核心成交字段
- 如券商更正成交，必须以 CorrectionEvent 形式处理
- Agent 只能生成成交差异分析，不得修改 Trade

---

## 15.3 StrategyInstance 状态机

状态：

- draft
- approved
- paper_running
- live_preparing
- pause_open
- live_running
- close_only
- stopped
- failed
- recovering

关键迁移：

|当前状态|允许迁移到|
|---|---|
|draft|approved, stopped|
|approved|paper_running, live_preparing, stopped|
|paper_running|approved, stopped, failed|
|live_preparing|pause_open, failed, stopped|
|pause_open|live_running, close_only, stopped, recovering|
|live_running|pause_open, close_only, recovering, failed, stopped|
|close_only|pause_open, stopped, recovering|
|recovering|pause_open, close_only, failed|
|failed|recovering, stopped|
|stopped|approved|

约束：

1. 进入 live_running 必须经过审批或明确规则授权
2. Agent 不得自动将策略恢复为 live_running
3. Agent 可创建恢复或上线 Proposal

---

## 15.4 Reconciliation 状态机

状态：

- pending
- running
- matched
- mismatch_detected
- corrected
- escalated
- closed

Agent 角色：

- 可分析 mismatch
- 可生成 correction proposal
- 不得直接执行 correction 生效

---

## 15.5 RecoverySession 状态机

状态：

- created
- loading_state
- reconciling
- rebuilding_context
- pending_confirmation
- completed
- aborted
- escalated

Agent 角色：

- 可生成恢复建议
- 可汇总异常链路
- 可协助生成恢复报告
- 不得绕过 pending_confirmation

---

## 15.6 AgentTask 状态机

状态：

- created
- planning
- running
- waiting_tool
- completed
- failed
- timeout
- canceled
- escalated

约束：

1. timeout 不得视为 completed
2. failed 不得自动重试有副作用步骤，除非具备幂等键和重试策略
3. escalated 必须通知人工或治理服务

---

## 15.7 AgentProposal 状态机

状态：

- drafted
- policy_checking
- policy_rejected
- pending_approval
- approved
- rejected
- execution_pending
- executed
- execution_failed
- expired
- canceled

关键迁移：

|当前状态|允许迁移到|
|---|---|
|drafted|policy_checking, canceled|
|policy_checking|policy_rejected, pending_approval, approved|
|pending_approval|approved, rejected, expired, canceled|
|approved|execution_pending, expired, canceled|
|execution_pending|executed, execution_failed, escalated|
|policy_rejected|终态|
|rejected|终态|
|executed|终态|
|expired|终态|
|canceled|终态|

约束：

1. policy_rejected 不得继续执行
2. expired 不得执行
3. Live 高风险 Proposal 不得跳过 pending_approval

---

## 15.8 ApprovalRequest 状态机

状态：

- pending
- approved
- rejected
- expired
- canceled

约束：

1. 审批结果必须不可篡改
2. 审批必须绑定审批快照
3. 审批通过不等于执行成功
4. 执行结果必须由 ControlledExecution 记录

---

# 16. 共享账户资金预占与释放模型

## 16.1 设计目标

解决：

- 多策略共享账户同时争抢资金
- 风控已通过但尚未下单期间的可用资金超承诺
- 下单失败后的资金释放
- 部分成交后的资金消费归因

---

## 16.2 资金预占原则

1. 新开仓必须先完成资金预占
2. 同一账户资金预占以 `account_id` 串行仲裁
3. 预占为本地风控执行语义，不等价于券商真实冻结
4. 风险判断时使用：
    - `QMT available_cash`
    - 减去 `active reservations`
    - 取保守值

---

## 16.3 Agent 边界

Agent 可以：

- 分析资金预占异常
- 生成释放建议
- 生成对账报告

Agent 不可以：

- 直接创建 CashReservation
- 直接释放 CashReservation
- 直接修改 consumed / released 状态
- 绕过 account_id 串行仲裁

---

# 17. Signal → Intent → Order 转换模型

## 17.1 转换链路

Text

Signal

→ DecisionSnapshot validation

→ Pre-Trade Risk

→ Cash Reservation

→ ExecutionIntent

→ Target-to-Order conversion

→ Final Pre-Submit Check

→ OrderRequest

→ QMT submit

→ Order / Trade updates

---

## 17.2 reference_price 定义

V1.3 继续要求 `reference_price` 必须配置来源：

可选优先级：

1. latest market price
2. last completed bar close
3. strategy-declared reference
4. fallback rejected

默认：

- Live 买入估算优先使用最新可用市场价
- 若行情滞后超阈值，则禁止新开仓
- 不允许使用过期 reference_price 推算数量

---

## 17.3 stale price 规则

若 reference_price 过期超过阈值：

- 新开仓：reject
- 平仓：可按更保守策略继续，需显式配置
- 必须告警

---

## 17.4 Agent 边界

Agent 不参与 Signal → Intent → Order 的直接转换。  
Agent 只能：

- 分析转换失败原因
- 生成异常报告
- 提出参数或规则调整 Proposal
- 不得直接生成 Live OrderRequest

---

# 18. 风控架构

## 18.1 分层

1. Pre-Trade Risk
2. In-Flight Risk
3. Runtime Risk
4. Post-Trade Risk

---

## 18.2 决策优先级

Text

force_flatten > reject > resize > delay > allow

---

## 18.3 `force_flatten` 语义

`force_flatten` 是风控动作，不依赖策略再生成 Signal。

其行为为：

1. 风控直接生成 Flatten ExecutionIntent
2. 跳过普通策略信号产生流程
3. 仍需经过 Final Pre-Submit Check
4. 默认允许绕过“禁止新开仓”限制，因为其本质为风险减仓/清仓
5. 若执行失败，必须升级告警并可重复尝试或人工接管

---

## 18.4 风控与 Agent 边界

Agent 可以：

- 做风险解释
- 做阈值建议
- 做异常归因
- 生成风控配置变更 Proposal

Agent 不可以：

- 替代风控引擎最终裁决
- 直接修改风控阈值
- 绕过风控生成执行意图
- 直接发起 force_flatten

---

# 19. Final Pre-Submit Check

## 19.1 定义

Final Pre-Submit Check 是真实调用 QMT 下单前最后不可绕过的同步检查点。

目的：

- 防止风控通过后到下单前状态变化
- 防止资金预占失效
- 防止 kill switch 生效后仍继续下单
- 防止信号过期订单仍提交
- 防止 Agent 或外部操作绕过执行内核

---

## 19.2 检查项

至少检查：

1. StrategyInstance 状态
2. Signal / ExecutionIntent 是否过期
3. QMT Adapter 是否可用
4. Account 状态是否正常
5. Position / available_quantity 是否足够
6. CashReservation 是否 active 且未过期
7. 是否已有冲突中的在途订单
8. 是否命中 kill switch / close_only
9. 是否满足订单频率限制
10. 订单参数合法性
11. OrderRequest 来源是否合法
12. 是否来自确定性执行服务

---

## 19.3 结果类型

- allow
- reject
- retry_later
- escalate_manual

---

## 19.4 执行要求

1. Final Check 必须同步执行
2. Final Check 不得被 Agent、策略或配置绕过
3. Final Check 失败必须写入审计和 Execution Journal
4. `retry_later` 不得无限重试
5. 非确定性服务生成的 OrderRequest 必须拒绝

---

# 20. Execution Service 与拒单分类

## 20.1 拒单分类 taxonomy

拒单原因至少分为：

1. network_error
2. adapter_internal_error
3. invalid_parameter
4. broker_reject
5. exchange_reject
6. market_untradable
7. price_out_of_limit
8. insufficient_cash
9. insufficient_position
10. risk_reject
11. duplicate_submit
12. unknown_reject
13. unauthorized_source
14. policy_blocked

---

## 20.2 补救策略

|拒单类型|默认动作|
|---|---|
|network_error|可限次重试|
|adapter_internal_error|可限次重试，超限升级|
|invalid_parameter|立即失败，禁止重试|
|broker_reject|默认失败，需分类分析|
|exchange_reject|默认失败|
|market_untradable|delay 或 reject|
|price_out_of_limit|价格重算一次或 reject|
|insufficient_cash|释放预占并 reject|
|insufficient_position|reject + 对账|
|risk_reject|reject|
|duplicate_submit|幂等拦截，查询状态|
|unknown_reject|uncertain / escalated|
|unauthorized_source|reject + 安全告警|
|policy_blocked|reject + 审计|

---

## 20.3 重试要求

- 重试必须保留同一业务主键链路
- 不得因重试生成新的逻辑订单而导致重复下单
- 重试前必须重新执行 Final Pre-Submit Check
- Agent 不得通过重复 Tool 调用触发重复实盘行为

---

# 21. 人工干预与外源交易处理规范

## 21.1 外源交易定义

以下行为视为外源交易：

1. 交易员在 QMT 手工下单
2. 非本系统其他程序下单
3. 券商侧补单、撤单或修正
4. 无法匹配到内部 order_request 的委托/成交

---

## 21.2 识别规则

若委托/成交满足以下任一条件，标记为 external/manual：

- 无可匹配 idempotency_key / remark
- 无可匹配时间窗口内内部 OrderRequest
- 数量、价格、方向与内部订单不匹配
- 账户端出现未知持仓变化

---

## 21.3 系统动作

检测到外源交易后：

1. 记录 ExternalManualEvent
2. 执行持仓/账户对账
3. StrategyInstance 至少进入 `pause_open`
4. 若影响重大，进入 `close_only` 或 `recovering`
5. 需要人工确认后才可恢复 `live_running`

---

## 21.4 Agent 角色

Agent 可以：

- 分析外源交易影响
- 生成对账报告
- 生成恢复建议
- 创建恢复 Proposal

Agent 不可以：

- 伪造内部 signal_id
- 直接把外源交易标记为内部正常订单
- 直接恢复 live_running

---

# 22. Live 启动、恢复与对账

## 22.1 启动顺序

1. 加载配置与审批状态
2. 校验时钟
3. 连接 QMT
4. 查询账户/持仓/当日委托/当日成交
5. 加载本地未完成状态
6. 恢复 CashReservation
7. 执行订单对账
8. 执行成交对账
9. 执行持仓对账
10. 检查外源交易
11. 重建 DecisionSnapshot / Strategy Context 必要部分
12. 建立 RecoverySession
13. 默认进入 `pause_open`
14. 等待人工或规则批准恢复

---

## 22.2 Reservation 恢复

恢复时必须检查：

- 活跃 reservation 是否有对应在途订单
- 是否已被成交消耗
- 是否应释放
- 是否 TTL 已过期

不允许盲目恢复所有预占为 active。

---

## 22.3 重启跨 Bar 规则

- 不自动补发过期实盘信号
- 可补建快照与上下文
- 必须从下一个合法 completed bar 恢复正式决策
- 如需历史重放，只能进入非实盘 replay 模式

---

## 22.4 Agent 在恢复中的角色

Agent 可参与：

- 恢复上下文汇总
- 异常链路解释
- 差异原因归因
- 恢复步骤建议
- 恢复报告生成

Agent 不可：

- 直接修改恢复状态机
- 直接完成 correction
- 直接恢复 Live 正常交易
- 绕过 pending_confirmation

---

# 23. Live 故障降级策略

## 23.1 降级模式

系统定义：

1. normal
2. pause_open
3. close_only
4. degraded_query_primary
5. emergency_stop

---

## 23.2 QMT 回报异常

- 切换到 `query_primary`
- 禁止高风险新开仓
- 加密查询频率进行对账
- 必要时进入 `pause_open`

---

## 23.3 QMT 查询异常

- 若回报仍正常，可暂维持 `event_primary`
- 若查询与回报均异常，进入 `degraded` / `close_only`

---

## 23.4 Live DB 不可用

默认规则：

- 禁止新开仓
- 禁止生成无法持久化的正式 OrderRequest
- 系统进入 `pause_open` 或 `close_only`

例外：

- 风控强平在显式启用 emergency journal 方案时，可允许执行
- 但必须具备本地持久化应急日志能力
- 默认 V1.3 不启用该能力，除非专项设计评审通过

---

## 23.5 Redis / Event Bus 不可用

- 若 DB 与本地关键路径正常，系统可继续运行
- 禁止依赖 Redis 作为唯一幂等判断
- 事件广播可降级为本地同步处理
- 必须告警

---

## 23.6 Agent Runtime 不可用

默认行为：

- 不影响 Live 主路径继续安全运行
- 停止 Agent 分析、报告、建议生成
- 禁止等待 Agent 结果才能执行必要风控
- 已 pending 的 Agent Proposal 保持原状态
- Live 恢复、上线、配置变更等需人工处理

---

## 23.7 Tool Gateway 不可用

默认行为：

- Agent 无法执行 Tool
- 只读分析可降级或停止
- 有副作用任务全部暂停
- 不影响交易内核已授权主路径

---

## 23.8 Approval Store 不可用

默认行为：

- 不允许新的 Live 高风险变更生效
- 已审批且已固化到 Live 配置的策略可继续运行
- 需要审批的恢复、上线、阈值修改全部阻塞
- 触发 P1 告警

---

## 23.9 Kill Switch

触发后：

1. 立即阻止新开仓
2. 撤销可撤开仓单
3. 根据配置发起平仓或保守停机
4. 进入 `emergency_stop` 或 `close_only`
5. Agent 不得阻止 Kill Switch 生效

---

# 24. Hermes Agent 架构与治理

## 24.1 Agent 系统定位

Hermes Agent 是受控智能编排层，用于：

- 研究编排
- 回测编排
- 验证与优化任务调度
- 监控分析
- 对账分析
- 恢复建议
- 审计报告
- 运维辅助

Hermes Agent 不是：

- 交易执行内核
- 风控最终裁决器
- 订单状态机
- QMT 下单代理
- 账户/持仓事实源

---

## 24.2 Agent 角色

建议角色：

1. Data Agent
2. Research Agent
3. Strategy Design Agent
4. Backtest Orchestration Agent
5. Validation Agent
6. Optimization Agent
7. Portfolio Analysis Agent
8. Monitoring Agent
9. Reconciliation Agent
10. Recovery Copilot Agent
11. Audit Reporting Agent
12. Orchestrator Agent

不建议使用以下命名作为生产权限角色：

- Execution Agent
- Risk Agent

若需要相关能力，应命名为：

- Execution Analysis Agent
- Risk Review Agent

并且仅限分析和建议。

---

## 24.3 Tool Gateway

Agent 所有工具调用必须经过 Tool Gateway。

Tool Gateway 职责：

1. 鉴权
2. 参数校验
3. Policy Check
4. 幂等控制
5. 速率限制
6. 环境隔离
7. 审计记录
8. 输出脱敏
9. 越权拦截

---

## 24.4 Tool 分类

### 只读工具

示例：

- query_market_data
- query_backtest_result
- query_strategy_status
- query_order_status
- query_position_snapshot
- query_reconciliation_diff
- query_audit_log

权限：

- 可自动调用
- 必须审计
- 不得返回超出任务范围的敏感信息

---

### 任务触发工具

示例：

- start_backtest
- start_validation
- start_paper_run
- start_reconciliation
- start_recovery_analysis
- create_approval_request
- generate_report

权限：

- 允许 Agent 触发
- 必须具备幂等键
- 必须记录 correlation_id

---

### 受控操作工具

示例：

- propose_pause_open
- propose_close_only
- propose_correction
- propose_risk_param_change
- propose_live_release
- propose_recovery_action

权限：

- 不直接执行生产变更
- 生成 AgentProposal
- 必须经过 Policy Check
- 可能需要 Approval

---

### 禁止工具

禁止向 Agent 暴露：

- qmt_submit_order
- qmt_cancel_order_direct
- update_order_state_direct
- update_trade_direct
- update_position_direct
- update_account_direct
- update_live_risk_threshold_direct
- restore_live_running_direct

---

## 24.5 Deterministic Validator / Policy Engine

所有 Live 相关 Proposal 必须经过 Deterministic Validator。

输出：

- pass
- fail
- manual_review_required

Policy Check 内容至少包括：

1. 环境权限
2. 角色权限
3. 目标对象状态
4. 动作是否允许
5. 是否需要审批
6. 是否违反风险边界
7. 是否具备版本绑定
8. 是否存在未解决异常
9. 是否处于交易时段限制
10. 是否超出 Agent 权限

---

## 24.6 Proposal / Approval / Controlled Execution 闭环

标准流程：

Text

AgentTask

→ ToolInvocation

→ AgentProposal

→ PolicyCheckResult

→ ApprovalRequest optional

→ ControlledExecution

→ AuditEvent

约束：

1. Proposal 不得直接修改生产状态
2. Policy fail 后必须终止
3. manual_review_required 必须进入审批
4. Approval approved 不等于执行成功
5. ControlledExecution 必须由确定性服务完成
6. 全流程必须可追踪

---

## 24.7 Agent 失败语义

Agent 失败规则：

1. 超时不得视为成功
2. 输出 JSON/schema 不合法不得继续
3. Tool 调用失败不得伪造成功
4. 只读任务失败可重试
5. 有副作用任务重试必须具备幂等键
6. Live 高风险任务失败默认 fail-closed
7. 多步骤任务部分成功时必须进入补偿或人工接管

---

## 24.8 Agent 资源隔离

交易时段内：

- 禁止 Agent 重型任务占用 Live 关键资源
- 禁止对 Live DB 发起分析型大查询
- 禁止竞争 account_id 级串行化资源
- 禁止执行影响 QMT Adapter 性能的任务

---

## 24.9 Agent 上下文安全

Agent 上下文必须遵守：

1. 最小上下文原则
2. 敏感凭证禁止注入
3. 账户敏感信息按需脱敏
4. 不跨环境复用未授权 memory
5. Agent memory 不得作为事实源
6. Prompt / workflow version 必须可追踪

---

# 25. Paper → Live 准入评估框架

## 25.1 准入原则

Paper 到 Live 不以“看起来差不多”为准，必须经过结构化评估。

---

## 25.2 必要维度

至少评估：

1. 信号一致率
2. 风控决策一致率
3. 目标持仓转换一致率
4. 下单成功率
5. 成交偏差率
6. 持仓偏差率
7. 数据延迟稳定性
8. 对账异常率
9. 系统可恢复性演练结果
10. Agent 参与建议的可追溯性
11. 一票否决项

---

## 25.3 最低观测要求

必须同时满足：

- 最短 Paper 观察期
- 最小有效交易样本数
- 覆盖不同市场状态的样本
- 至少一次恢复/重启演练
- 至少一次外源交易识别演练
- 至少一次重复事件/乱序事件演练
- 至少一次 Agent 越权拦截测试
- 至少一次 Agent Proposal 审批闭环测试

---

## 25.4 一票否决项示例

包括但不限于：

- 重复下单风险未解决
- 持仓对账不稳定
- 外源交易无法识别
- Final Pre-Submit Check 可被绕过
- DB 故障下行为不明确
- QMT 回报乱序导致状态机错误
- Agent 可绕过审批或直接影响 Live 状态
- Agent Tool 调用无法审计

---

# 26. 审计与版本治理

## 26.1 全链路可追溯

每笔真实订单必须可追溯到：

Text

Order

<- OrderRequest

<- Final Pre-Submit Check Result

<- CashReservation

<- ExecutionIntent

<- RiskCheckResult

<- Signal

<- DecisionSnapshot

<- FeatureSnapshot

<- StrategyInstance

<- VersionBinding

若存在 Agent 参与分析或建议，还必须可追溯到：

Text

AgentTask

<- ToolInvocation

<- AgentProposal

<- PolicyCheckResult

<- ApprovalRequest

<- ControlledExecution

<- AuditEvent

---

## 26.2 版本绑定

必须绑定：

- data_version
- feature_version
- strategy_version
- param_version
- risk_rule_version
- execution_policy_version
- engine_version
- qmt_adapter_version
- agent_workflow_version
- tool_version
- prompt_version
- live_config_version

---

## 26.3 审批对象

需审批：

- 策略首次 Live
- Live 恢复
- 风控核心参数变化
- 执行策略变化
- 共享账户额度变化
- QMT 节点切换
- emergency policy 启用
- Agent 提出的高风险 Live Proposal

---

## 26.4 Agent 审计要求

必须记录：

- Agent 身份
- Agent 角色
- workflow_version
- prompt_version
- tool_version
- 输入引用
- 输出引用
- Tool 调用参数摘要
- Tool 调用结果摘要
- Policy Check 结果
- Approval 结果
- ControlledExecution 结果
- 越权尝试
- 重试与补偿记录

---

# 27. 安全设计

## 27.1 凭证隔离

- QMT 凭证仅在 Live / QMT Node 持有
- Agent 无下单凭证
- 凭证加密存储
- 凭证使用留痕
- Tool Gateway 不向 Agent 返回凭证

---

## 27.2 角色权限

角色：

- Researcher
- Trader
- Risk Manager
- Admin
- Auditor
- Agent Service Account
- Tool Gateway Service Account
- Controlled Execution Service Account

最小权限原则适用全系统。

---

## 27.3 Agent Service Account 权限

Agent Service Account 默认权限：

允许：

- 调用白名单只读工具
- 调用任务触发工具
- 创建 Proposal
- 创建 ApprovalRequest

禁止：

- 直接写 Live Operational DB
- 直接调用 QMT
- 直接修改风控阈值
- 直接修改策略状态为 live_running
- 直接修改订单、成交、持仓、账户

---

# 28. 可观测性与告警

## 28.1 交易内核监控

监控：

- QMT 连接状态
- 回报延迟
- 查询延迟
- 下单失败率
- 拒单率
- 对账差异
- 持仓偏差
- 账户风险
- CashReservation 异常
- Final Pre-Submit Check 拒绝率

---

## 28.2 Agent 监控

监控：

- AgentTask 数量
- AgentTask 超时率
- ToolInvocation 失败率
- ToolInvocation 越权拦截次数
- Proposal pending 数量
- Approval pending 数量
- Policy rejection 数量
- Agent 重试次数
- Agent 资源占用
- Live 交易时段 Agent 查询量

---

## 28.3 告警等级

- P0：立即停机 / 仅平仓
- P1：立即人工介入
- P2：盘中关注，收盘处理
- P3：信息提醒

Agent 越权尝试默认不低于 P1。

---

# 29. 测试与故障演练要求

## 29.1 状态机测试

必须覆盖：

- Order 非法迁移拒绝
- uncertain 修正
- 查询结果 correction
- StrategyInstance 恢复流程
- AgentProposal 非法迁移拒绝
- ApprovalRequest 状态不可篡改

---

## 29.2 资金预占测试

必须覆盖：

- 双策略并发抢资金
- 预占后下单失败释放
- 部分成交消耗与剩余释放
- TTL 过期释放
- Agent 无法直接释放预占

---

## 29.3 决策快照测试

必须覆盖：

- FeatureSnapshot 缺失阻断
- 横截面快照不完整
- partial_allowed 策略行为验证
- Agent 无法伪造正式 DecisionSnapshot

---

## 29.4 人工干预测试

必须覆盖：

- 手工买入
- 手工卖出
- 手工撤单
- 未知成交识别
- Agent 只能生成恢复建议

---

## 29.5 降级测试

必须覆盖：

- DB 不可用进入 pause_open / close_only
- Redis 不可用但不重复下单
- 回报异常切 query_primary
- Agent Runtime 不可用
- Tool Gateway 不可用
- Approval Store 不可用
- kill switch 生效

---

## 29.6 Agent 安全测试

必须覆盖：

1. Agent 尝试直接下单被拒绝
2. Agent 尝试直接修改订单状态被拒绝
3. Agent 尝试直接恢复 live_running 被拒绝
4. Agent Proposal 未审批不得执行
5. Policy fail 的 Proposal 不得执行
6. Agent 超时不得触发生产副作用
7. Tool 重试不得产生重复副作用
8. Agent 输出 schema 错误不得进入执行
9. Live 交易时段 Agent 大查询被限制
10. 越权尝试留痕并告警

---

## 29.7 上线前演练

必须覆盖：

1. QMT 重启
2. 网络闪断
3. 回报乱序
4. 成交回报丢失
5. DB 不可用
6. Redis 不可用
7. 多策略共享账户抢资金
8. 外源手工平仓
9. 恢复后 pause_open → live_running
10. kill switch
11. Agent Runtime 故障
12. Tool Gateway 故障
13. Agent 越权拦截
14. Proposal / Approval / ControlledExecution 闭环

---

# 30. 实施优先级

## 30.1 P0

1. 核心状态机
2. Live Operational DB
3. QMT Adapter PoC
4. CashReservation
5. Final Pre-Submit Check
6. 恢复与对账
7. 外源交易识别
8. AuditEvent 基础设施
9. Agent 权限边界硬隔离
10. Tool Gateway 最小实现

---

## 30.2 P1

1. 回测引擎
2. Paper 引擎
3. DecisionSnapshot
4. 风控分层
5. 监控告警
6. 审批与治理
7. AgentTask / ToolInvocation / AgentProposal 数据模型
8. Policy Engine
9. Proposal / Approval / ControlledExecution 闭环

---

## 30.3 P2

1. Agent 自动化研究
2. 报告系统
3. 高级组合控制
4. 高级分析平台
5. Recovery Copilot 增强
6. Reconciliation Agent 增强
7. 自动化根因分析

---

# 31. 架构风险与接受条件

## 31.1 主要风险

1. QMT 非标准接口行为
2. 回报与查询差异
3. 多策略共享账户复杂性
4. 人工干预污染状态
5. Paper 与 Live 环境偏差
6. 故障降级策略执行不一致
7. Agent Tool 权限误配
8. Agent 输出被误认为事实源
9. Agent 大查询影响 Live 性能
10. Proposal / Approval 流程缺失导致越权

---

## 31.2 接受条件

进入正式开发前，至少需补齐：

1. 数据库 DDL 草案
2. 核心状态机设计文档
3. QMT Adapter 技术方案
4. 故障降级 SOP
5. 测试计划 V1.0
6. Agent Tool 权限清单
7. Agent 数据模型 DDL
8. Proposal / Approval / ControlledExecution API 草案
9. Agent 越权测试用例
10. 审计事件规范

---

# 32. SAD V1.3 与 V1.2 的主要差异

|领域|V1.2|V1.3|
|---|---|---|
|Agent 定位|辅助研究与治理|受控智能编排层，明确非交易内核|
|Agent 权限|原则性禁止直接下单|增加 Tool Gateway、Policy Engine、Proposal 闭环|
|数据模型|交易核心对象为主|增加 AgentTask、AgentProposal、ToolInvocation、ControlledExecution|
|Live 主路径|已定义最小可信链路|明确 Agent 不得进入同步主路径|
|失败语义|主要关注交易故障|增加 Agent timeout、tool failure、fail-closed|
|审计|订单与版本审计|增加 Agent 全链路审计|
|测试|状态机、预占、恢复|增加 Agent 越权、Proposal 审批、Tool 幂等测试|
|安全|凭证隔离|增加 Agent Service Account 最小权限与 Tool Gateway 隔离|

---

# 33. 结论

SAD V1.3 的核心目标是将 HQMTS 架构进一步收敛为：

> **确定性交易内核负责实盘，Hermes Agent 负责受控编排、分析、建议和报告。**

V1.3 的关键架构结论如下：

1. 正式 Signal 必须绑定可重建的 DecisionSnapshot
2. 多策略共享账户必须通过 CashReservation 串行仲裁
3. 真实下单前必须经过 Final Pre-Submit Check
4. Order / Strategy / Reconciliation / Recovery 必须遵守明确状态机
5. 人工干预必须被识别为外源交易并触发降级与审计
6. DB 不可用时默认禁止新开仓
7. 事件系统依赖幂等、串行化和状态机，而不是 exactly-once
8. `force_flatten` 是风控动作，不依赖策略二次确认
9. Paper → Live 必须有结构化准入框架
10. 恢复后默认 `pause_open`，不得自动冒进恢复
11. Hermes Agent 不得进入实盘下单主路径
12. Agent 只能通过 Tool Gateway 和 Proposal / Approval / ControlledExecution 闭环作用系统
13. Agent 输出不是事实源，不能替代交易数据库、审计系统和状态机
14. Agent 超时、失败、越权或上下文不完整时，Live 相关动作默认 fail-closed