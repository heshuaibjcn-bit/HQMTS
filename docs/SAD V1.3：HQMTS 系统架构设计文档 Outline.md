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

1. 明确 **Hermes Agent 是受控智能编排层，不是交易确定性内核**
2. 强化 **确定性交易内核** 的中心地位
3. 明确 Agent 只能通过 **白名单 Tool / Control API / Transition API** 间接作用系统
4. 增加 **AgentTask / AgentProposal / ToolInvocation / ApprovalRequest** 等治理对象
5. 建立 **Proposal → Policy Check → Approval → Controlled Execution → Audit** 闭环
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

V1.3 系统分为 11 层：

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
11. 用户界面层（Web Dashboard + AI 对话）

---

## 4.2 推荐逻辑架构图

Text

  ┌─────────────────────────────────────────────────────────┐

  │                    User Interface Layer                   │

  │           Web Dashboard  │  AI Chat Interface            │

  │    REST API + WebSocket  │  SSE (Streaming)               │

  └──────────────────────────────┬──────────────────────────┘

                                 │

                  ┌───────────────▼───────────────┐

                  │        Hermes Agent Layer       │

                  │ Research / Analysis / Report    │

                  │ Reconciliation / Recovery       │

                  └───────────────┬───────────────┘

                                  │

                     Tool / Proposal / Approval API

                                  │

                  ┌───────────────▼───────────────┐

                  │      Governance & Control       │

                  │ Policy / Approval / Audit       │

                  └───────────────┬───────────────┘

                                  │

        ┌─────────────────────────▼─────────────────────────┐

        │              Deterministic Trading Core              │

        │ Strategy Runtime / Risk / Reservation / Execution    │

        │ Order FSM / Trade Ledger / Reconciliation            │

        └───────────────┬──────────────────────┬────────────┘

                        │                      │

               ┌────────▼────────┐     ┌──────▼────────┐

               │   Data Layer     │     │   QMT Adapter │

               │ Tushare / Bars   │     │ Market/Trade  │

               └─────────────────┘     └───────────────┘

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

状态（5 个）：

- pending
- executing
- completed
- failed
- expired

合法迁移：

|当前状态|允许迁移到|
|---|---|
|pending|executing, expired|
|executing|completed, failed|
|completed|终态|
|failed|终态|
|expired|终态|

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

- 业务展示使用 `Asia/Shanghai`
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
|traded_at|成交时间|QMT成交回报/查询|
|snapshot_time|账户/持仓快照时间|查询时刻|
|agent_task_started_at|Agent 任务开始时间|Agent Runtime|
|tool_invoked_at|Tool 调用开始时间|Tool Gateway|
|approval_decision_at|审批决策时间|Approval Service|

---

## 9.3 时钟同步要求

- Live 节点必须启用时间同步
- 时间偏移超阈值触发告警
- 偏移严重时进入 `pause_open`
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

状态（10 个）：

- pending
- submitted
- accepted
- partial_filled
- filled
- canceled
- rejected
- error
- suspended
- expired

合法迁移：

|当前状态|允许迁移到|
|---|---|
|pending|submitted, canceled|
|submitted|accepted, rejected, canceled|
|accepted|partial_filled, filled, canceled|
|partial_filled|partial_filled, filled, canceled|
|filled|终态|
|canceled|终态|
|rejected|终态|
|error|accepted, partial_filled, filled, canceled, rejected, expired|
|suspended|accepted, canceled|
|expired|终态|

约束：

1. `error` 为恢复或乱序修正的过渡态，可恢复到多种终态
2. `suspended` 为交易所/券商侧暂停状态，可恢复或撤销
3. 非法迁移必须被拒绝并记录审计
4. 查询结果可触发 correction 迁移，但必须留痕
5. Agent 不得直接触发 Order 状态迁移

---

## 15.2 Trade 幂等规则

- Trade 以 `broker_trade_id` 为幂等主键
- 同一 `broker_trade_id` 重复到达必须忽略重复写入
- Trade 一经确认，不允许修改核心成交字段
- 如券商更正成交，必须以 CorrectionEvent 形式处理
- Agent 只能生成成交差异分析，不得修改 Trade

---

## 15.3 StrategyInstance 状态机

状态（10 个）：

- draft
- backtest_ready
- validation_ready
- paper_running
- live_running
- pause_open
- close_only
- stopped
- paused
- archived

关键迁移：

|当前状态|允许迁移到|
|---|---|
|draft|backtest_ready, archived|
|backtest_ready|validation_ready, draft, archived|
|validation_ready|paper_running, backtest_ready, archived|
|paper_running|live_running, validation_ready, paused, archived|
|live_running|pause_open, close_only, stopped, archived|
|pause_open|live_running, close_only, stopped|
|close_only|pause_open, stopped|
|stopped|draft, archived|
|paused|paper_running, stopped|
|archived|终态|

约束：

1. 进入 live_running 必须经过审批或明确规则授权
2. Agent 不得自动将策略恢复为 live_running
3. Agent 可创建恢复或上线 Proposal
4. `archived` 为唯一终态

---

## 15.4 Reconciliation 状态机

状态（9 个）：

- initialized
- comparing
- matched
- mismatched
- adjusting
- completed
- failed
- canceled
- escalated

合法迁移：

|当前状态|允许迁移到|
|---|---|
|initialized|comparing, canceled|
|comparing|matched, mismatched, failed|
|matched|completed|
|mismatched|adjusting, escalated|
|adjusting|completed, failed|
|completed|终态|
|failed|终态|
|canceled|终态|
|escalated|终态|

Agent 角色：

- 可分析 mismatched 差异
- 可生成 correction proposal
- 不得直接执行 correction 生效

---

## 15.5 RecoverySession 状态机

状态（7 个）：

- created
- diagnosing
- recovering
- verifying
- completed
- failed
- canceled

合法迁移：

|当前状态|允许迁移到|
|---|---|
|created|diagnosing, canceled|
|diagnosing|recovering, failed, canceled|
|recovering|verifying, failed|
|verifying|completed, recovering, failed|
|completed|终态|
|failed|终态|
|canceled|终态|

Agent 角色：

- 可生成恢复建议
- 可汇总异常链路
- 可协助生成恢复报告
- 不得绕过 verifying 人工确认

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
|policy_checking|policy_rejected, pending_approval, approved, canceled|
|pending_approval|approved, rejected, expired, canceled|
|approved|execution_pending|
|execution_pending|executed, execution_failed, expired|
|policy_rejected|终态|
|rejected|终态|
|executed|终态|
|execution_failed|终态|
|expired|终态|
|canceled|终态|

约束：

1. policy_rejected 不得继续执行
2. expired 不得执行
3. Live 高风险 Proposal 不得跳过 pending_approval
4. execution_failed 为终态

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
2. 同一账户资金预占以 `account_id` 串行仲裁
3. 预占为本地风控执行语义，不等价于券商真实冻结
4. 风险判断时使用：
    - `QMT available_cash`
    - 减去 `active reservations`
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

## 18.3 `force_flatten` 语义

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
4. `retry_later` 不得无限重试
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
15. kill_switch
16. signal_expired
17. strategy_not_live
18. market_closed
19. order_frequency_exceeded

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
|unknown_reject|error / escalated|
|unauthorized_source|reject + 安全告警|
|policy_blocked|reject + 审计|
|kill_switch|reject + 立即告警 + 停止新开仓|
|signal_expired|reject + 告警|
|strategy_not_live|reject + 状态检查|
|market_closed|reject + 告警|
|order_frequency_exceeded|reject + 限流告警|

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
3. StrategyInstance 至少进入 `pause_open`
4. 若影响重大，进入 `close_only` 或 `stopped`
5. 需要人工确认后才可恢复 `live_running`

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
13. 默认进入 `pause_open`
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
- 绕过 verifying（人工确认环节）

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

- 切换到 `query_primary`
- 禁止高风险新开仓
- 加密查询频率进行对账
- 必要时进入 `pause_open`

---

## 23.3 QMT 查询异常

- 若回报仍正常，可暂维持 `event_primary`
- 若查询与回报均异常，进入 `degraded` / `close_only`

---

## 23.4 Live DB 不可用

默认规则：

- 禁止新开仓
- 禁止生成无法持久化的正式 OrderRequest
- 系统进入 `pause_open` 或 `close_only`

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
4. 进入 `emergency_stop` 或 `close_only`
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
- error 状态修正
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

# 29.5. 用户界面架构

## 29.5.1 系统定位

用户界面层是 HQMTS 的第 11 层，位于存储与可观测层之上，是用户（量化研究者、交易执行者、系统管理者）与系统交互的唯一入口。

定位约束：

- UI 层是后端 API 的纯消费者，不承载任何业务逻辑、交易决策或风控裁决
- Dashboard 与 AI Chat 共享同一套 REST API 和 WebSocket 通道
- UI 层不直接访问数据库、不直接调用 QMT、不直接读写交易状态
- 所有写操作通过后端 API 走完整治理链路

## 29.5.2 架构分层

用户界面层内部按职责分为 3 个子层：

```
┌──────────────────────────────────────────────────────┐
│                    Presentation Layer                  │
│  ┌──────────────────┐  ┌────────────────────────────┐ │
│  │  Web Dashboard    │  │  AI Chat Interface         │ │
│  │  (SPA / SSR)      │  │  (Conversation + SSE)      │ │
│  └────────┬──────────┘  └──────────┬─────────────────┘ │
│           │                        │                    │
│  ┌────────▼────────────────────────▼─────────────────┐ │
│  │              API Client Layer                       │ │
│  │  REST Client  │  WebSocket Client  │  SSE Client   │ │
│  └────────┬──────────────────────────┬───────────────┘ │
│           │                          │                  │
│  ┌────────▼──────────────────────────▼───────────────┐ │
│  │              State Management Layer                 │ │
│  │  Local Cache  │  Real-time Sync  │  Optimistic UI  │ │
│  └───────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
                          │
                 ┌────────▼────────┐
                 │  FastAPI Backend │
                 │  REST + WS + SSE │
                 └─────────────────┘
```

### Presentation Layer

- **Web Dashboard**：页面路由、组件渲染、图表可视化
- **AI Chat Interface**：对话流渲染、Markdown 支持、工具调用可视化

### API Client Layer

- **REST Client**：调用 FastAPI REST 端点，处理认证、重试、错误
- **WebSocket Client**：接收实时推送（持仓变动、订单状态、信号、告警）
- **SSE Client**：接收 AI 对话流式输出

### State Management Layer

- **Local Cache**：减少重复 API 调用（策略列表、标的列表等低频变更数据）
- **Real-time Sync**：WebSocket 消息合并到本地状态
- **Optimistic UI**：仅用于非交易数据（Chat 消息发送状态、UI 面板折叠）。**禁止对 Order、Position、Account、RiskCheckResult 状态使用 Optimistic Update**，撤单、下单、策略启停必须等服务端确认后再更新界面

Optimistic UI 约束：
- 若后端确认与 Optimistic 状态冲突，必须强制回退并提示用户
- 原因：在撤单-重试场景中，Optimistic 显示"已取消"但后端实际已成交，可能导致用户基于幻觉数据提交重复订单

## 29.5.3 后端接口扩展

用户界面层依赖以下后端接口，其中部分已存在，部分需新增。

### 已有 REST API（可直接复用）

| 端点 | 用途 |
|------|------|
| `GET /` | 系统信息 |
| `GET /health` | 健康状态 |
| `GET /instruments/` | 标的列表 |
| `GET /orders/` | 订单列表 |
| `GET /signals/` | 信号列表 |
| `GET /strategies/` | 策略列表 |
| `GET /risk/status` | 风控状态 |
| `POST /risk/kill-switch` | 激活 Kill Switch（REST 同步返回，不依赖 WebSocket） |
| `POST /risk/kill-switch/deactivate` | 停用 Kill Switch（需审批，见 PRD 7.4） |
| `POST /risk/flatten` | 触发平仓 |
| `GET /backtest/` | 回测列表 |
| `POST /backtest/run` | 发起回测 |
| `GET /audit/events` | 审计事件 |
| `POST /validation/admission` | 准入管理 |

### 需新增接口

**FR-API-001 WebSocket 端点 `/ws`**

```
连接：GET /ws
请求头：Sec-WebSocket-Protocol: bearer, {token}
（禁止通过 query parameter 传递 token，避免泄露到服务器日志）

消息格式（服务端推送）：
{
  "type": "position_update" | "order_update" | "signal_new" |
          "risk_change" | "alert" | "agent_task_update",
  "data": { ... },
  "event_id": "evt_abc123",
  "sequence": 1001,
  "timestamp": "ISO-8601"
}
```

推送事件类型：

| type | 触发时机 | 推送数据 |
|------|---------|---------|
| `position_update` | 持仓价格变动或数量变动 | position_id, market_price, unrealized_pnl |
| `order_update` | 订单状态变更 | order_id, old_status, new_status |
| `signal_new` | 新信号生成 | signal_id, strategy, instrument, type |
| `risk_change` | 风控状态变更 | layer, old_status, new_status |
| `alert` | 告警触发 | alert_level, message, source |
| `agent_task_update` | Agent 任务状态变更 | task_id, old_status, new_status |

实现要求：

- 基于现有 `PipelineBus`（`infra/bus.py`）扩展，将 Redis Stream 消息桥接到 WebSocket
- 每个连接维护订阅过滤（用户角色决定可见事件范围，过滤规则见 PRD 30.6 FR-REALTIME-001）
- 双向应用层心跳：客户端每 30s 发送 `{"type": "ping"}`，服务端回复 `{"type": "pong"}`；服务端 60s 未收到 ping 则主动断开
- 重连时客户端发送 `{"type": "reconnect", "last_sequence": N}`，服务端补发缺失消息
- 服务端保留每个用户最近 100 条推送消息（TTL 5min）用于重连恢复
- 若缺失消息超出保留范围，发送完整状态快照
- 前端按 sequence 单调递增处理消息，乱序消息丢弃
- REST API 响应包含 `last_sequence` 字段，前端据此判断 REST 与 WebSocket 状态新旧
- 同一用户最多 3 个并发登录会话，每个会话可建立 1 个 WebSocket 连接（即最多 3 个 WebSocket 连接）
- WebSocket 是只读推送通道，客户端不能通过 WebSocket 发送操作命令

**FR-API-002 账户聚合端点 `GET /account/summary`**

```
响应：
{
  "account_id": "...",
  "total_asset": "1000000.00",
  "available_cash": "500000.00",
  "frozen_cash": "50000.00",
  "market_value": "450000.00",
  "pnl_intraday": "12000.00",
  "pnl_intraday_pct": "1.2",
  "drawdown_intraday": "0.008",
  "position_count": 5,
  "active_strategies": 3,
  "updated_at": "ISO-8601"
}
```

**FR-API-003 AI 对话端点**

```
POST /chat/sessions          创建对话会话
GET  /chat/sessions          列出会话
POST /chat/sessions/{id}/messages  发送消息（SSE 流式响应）
GET  /chat/sessions/{id}/messages  获取历史消息
```

SSE 流式消息格式：

```
event: token
data: {"content": "当前持仓"}

event: tool_call
data: {"tool": "query_positions", "status": "running"}

event: tool_result
data: {"tool": "query_positions", "result": {...}}

event: approval_request
data: {"proposal_id": "...", "type": "...", "payload": {...}}

event: done
data: {"message_id": "..."}
```

**FR-API-004 告警端点 `GET /alerts`**

```
GET /alerts?level=P0&P1&status=unacknowledged

响应：
{
  "alerts": [
    {
      "alert_id": "...",
      "level": "P1",
      "message": "订单拒绝率超过阈值",
      "source": "risk",
      "created_at": "ISO-8601",
      "acknowledged": false
    }
  ]
}

POST /alerts/{alert_id}/acknowledge  确认告警
```

## 29.5.4 AI Chat 架构

### 对话链路

```
用户输入
  │
  ▼
前端 Chat UI ──POST /chat/sessions/{id}/messages──▶ Chat Router (FastAPI)
                                                      │
                                            ┌─────────▼──────────┐
                                            │  Chat Session Mgr   │
                                            │  (上下文管理)        │
                                            └─────────┬──────────┘
                                                      │
                                            ┌─────────▼──────────┐
                                            │  LLM Adapter       │
                                            │  Claude / OpenAI / │
                                            │  Local Model       │
                                            └─────────┬──────────┘
                                                      │ (function calling)
                                            ┌─────────▼──────────┐
                                            │  Tool Gateway      │
                                            │  (与 Agent 共享实例) │
                                            └─────────┬──────────┘
                                                      │
                                            ┌─────────▼──────────┐
                                            │  Policy Engine     │
                                            │  (与 Agent 共享实例) │
                                            └─────────┬──────────┘
                                                      │
                                            ┌─────────▼──────────┐
                                            │  [approved tool]   │
                                            │  or                │
                                            │  ApprovalRequest   │
                                            └────────────────────┘
```

Chat 流中的工具调用**不经过 Hermes Agent 编排层**。Chat 直接调用 ToolGateway（与 Agent 共享同一实例），ToolGateway 识别来源为 `chat_session`，创建 ToolInvocation 审计记录，走相同的 PolicyEngine 校验链路。

AgentTask 创建职责：
- **ChatSessionManager** 负责创建 AgentTask（source=`chat`）
- AgentTask.creator = 当前登录用户的 user_id
- AgentTask.metadata 包含：`chat_session_id`、`chat_message_id`、触发用户消息摘要
- AgentTask 状态由 ToolGateway 回调更新，ChatSessionManager 监听状态变更以推送 SSE 事件
- 一个用户消息可能触发 0 或 1 个 AgentTask（纯闲聊不创建 AgentTask，工具调用才创建）

关键区别：
- Agent 自动调用：由 AgentTask 驱动，有编排逻辑
- Chat 用户调用：由用户消息驱动，无编排逻辑，但走相同治理链路
- 两者共享 ToolGateway、PolicyEngine、ApprovalRequest 基础设施
- 两者产生独立的 ToolInvocation 审计记录（source 字段区分 `agent_task` vs `chat_session`）
- Chat 工具调用创建 AgentTask（source=chat）和 ToolInvocation 记录，与 Agent 自动化调用使用同一审计模型

### LLM Adapter

- 抽象层：统一 Claude API / OpenAI API / 本地模型（Ollama）的调用接口
- 流式输出：所有模型统一使用 SSE 流式返回
- 上下文管理：对话历史存储在服务端，前端只维护 session_id
- Token 限制：单次上下文不超过模型限制，超出时截断最早的消息
- 所有 LLM 调用的 prompt 和响应必须写入审计存储（保留 90 天，与 PRD FR-CHAT-006 对齐）

### Tool Executor（复用 ToolGateway）

- Chat 流直接调用 Hermes Agent 的 ToolGateway 和 PolicyEngine（共享实例，不创建新组件）
- 用户在 Chat 中的操作走与 Agent 相同的治理链路
- LLM 通过 function calling 决定调用哪些工具
- 工具调用结果流式返回前端（`tool_call` / `tool_result` SSE 事件）
- 每次 Chat 工具调用创建 AgentTask（source=chat）和 ToolInvocation 审计记录

### 审批流集成

- LLM 返回的 Proposal 通过 `approval_request` SSE 事件推送到前端
- 前端渲染审批卡片，用户点击审批/拒绝
- 审批操作调用已有 `POST /validation/admission/{id}/approve` 等端点
- 审批结果通过 WebSocket 实时推送到 Dashboard

## 29.5.5 前端状态管理

### 数据分类

| 数据类型 | 来源 | 更新策略 | 示例 |
|---------|------|---------|------|
| 静态配置 | REST API | 页面加载时拉取，手动刷新 | 策略列表、标的列表 |
| 实时状态 | WebSocket | 自动推送更新 | 持仓价格、订单状态 |
| 历史数据 | REST API | 按需加载，分页 | 审计事件、历史订单 |
| 流式数据 | SSE | 持续接收 | AI 对话输出 |

### 缓存策略

- **策略列表、标的列表**：本地缓存 5 分钟，避免重复请求
- **持仓数据**：WebSocket 推送增量更新，初始加载走 REST
- **订单数据**：WebSocket 推送状态变更，详情按需加载

### 环境视角

前端根据当前环境（Research / Backtest / Paper / Live）切换数据范围和操作权限：

- Research / Backtest：只读为主，隐藏实时监控面板
- Paper：显示实时监控，隐藏资金操作
- Live：全功能可用，敏感操作需二次确认

## 29.5.6 安全架构

### 认证与授权

- API 认证：Bearer Token（JWT），通过 `/auth/login` 获取
- WebSocket 认证：通过 Sec-WebSocket-Protocol 请求头传递 token（`Sec-WebSocket-Protocol: bearer, {token}`），禁止 query parameter 传递（避免泄露到服务器日志）
- SSE 认证：请求头携带 Bearer Token
- Token 过期自动刷新，刷新失败跳转登录页

### 前端安全

- 前端不存储敏感凭证（API Key、数据库密码、QMT 凭证）
- Live 环境敏感操作（Kill Switch、Force Flatten、策略启停）需二次确认弹窗
- CSRF 保护：SameSite Cookie + CSRF Token
- XSS 防护：对话内容严格转义，Markdown 渲染禁用 raw HTML

### 权限控制

- 前端根据用户角色（量化研究者 / 交易执行者 / 系统管理者）显示/隐藏功能
- 权限判断在后端 API 层执行，前端隐藏仅为 UX 优化，非安全边界
- 前端角色信息从 `/auth/me` 端点获取
- 详细权限矩阵见 PRD 30.3，SAD 实现与 PRD 定义保持一致
- 环境视角权限差异：Research/Backtest 只读为主，Paper 显示实时监控但隐藏资金操作，Live 全功能可用

## 29.5.7 可观测性

### 前端监控

- 页面加载性能（Core Web Vitals）
- API 调用成功率和延迟
- WebSocket 连接状态和重连次数
- AI 对话响应时间

### 错误处理

- API 错误：统一错误拦截，P0/P1 级别弹窗提示，P2/P3 级别 toast 提示
- WebSocket 断线：自动重连（指数退避，最大 30s），断线期间显示状态指示
- SSE 断流：自动重连，从中断点继续
- 网络不可用：显示离线状态，缓存最后已知数据

## 29.5.8 部署架构

### 开发环境

```
Frontend Dev Server (localhost:3000)
        │
        │ CORS / Proxy
        ▼
FastAPI Backend (localhost:8000)
```

### 生产环境

```
┌─────────────────────────────────────────┐
│              Nginx / Reverse Proxy       │
│  /           → Frontend Static Files     │
│  /api/*      → FastAPI Backend           │
│  /ws         → FastAPI WebSocket         │
│  /chat/*     → FastAPI SSE               │
└─────────────────────────────────────────┘
```

- 前端构建为静态文件，由 Nginx 托管
- API 请求通过 Nginx 反向代理到 FastAPI
- WebSocket 和 SSE 通过 Nginx 升级协议透传
- HTTPS / WSS 由 Nginx 终结 TLS

## 29.5.9 UI 与 Agent 边界

用户界面层与 Hermes Agent 的交互边界：

| 维度 | UI 层职责 | Agent 层职责 |
|------|----------|-------------|
| 数据查询 | 展示 API 返回的数据 | 通过 ToolGateway 查询 |
| 操作触发 | 发送操作请求到 API | 通过 PolicyEngine 校验 |
| 审批 | 展示审批卡片、收集用户决策 | 生成 ApprovalRequest、记录审批结果 |
| 分析 | 展示 Agent 返回的分析结果 | 执行分析逻辑、生成 Proposal |
| 风控 | 展示风控状态、提供操作入口 | 执行风控裁决、触发降级 |

约束：

- UI 层不得绕过 API 直接操作交易状态
- UI 层不得在客户端执行风控逻辑
- UI 层的"审批"操作只是收集用户意图，实际状态变更由后端执行
- AI Chat 中的 LLM 选择不影响后端 Agent 治理链的 Policy Engine 校验
- 所有 UI 操作产生的审计事件与核心审计系统（Section 26）使用同一存储

## 29.5.9.1 UI 层可观测性（补充 Section 28）

后端监控指标：

- WebSocket 活跃连接数 / 总连接尝试 / 连接失败率
- WebSocket 推送延迟（PipelineBus → 客户端 RTT 估算）P50 / P95 / P99
- Bridge 组件消息积压量
- SSE 活跃流数量
- Chat session 创建速率
- LLM API 调用延迟（P50 / P95 / P99）
- LLM API 错误率（按 provider 分类）
- LLM Token 消耗量
- Alert 产生和确认延迟
- 新增 REST API 端点延迟（/chat/*, /alerts, /account/summary）

前端监控指标：

- 页面加载性能（Core Web Vitals: LCP, FID, CLS）
- API 调用成功率和延迟
- WebSocket 连接状态和重连次数
- AI 对话响应时间

## 29.5.10 领域模型补充

Chat 和 Alert 相关领域模型，补充 Section 7。

### ChatSession

最小字段：

- session_id (PK)
- user_id
- title
- status: active / idle / archived
- model_provider（claude / openai / local）
- environment（research / backtest / paper / live）
- created_at
- updated_at

状态机：active → idle（30 分钟无消息）→ archived（用户手动归档或 7 天无活动）

### ChatMessage

最小字段：

- message_id (PK)
- session_id (FK)
- role: user / assistant / tool_call / tool_result / system
- content
- tool_call_id (nullable, 关联 ToolInvocation)
- agent_task_id (nullable, 关联 AgentTask，Chat 触发的工具调用创建 AgentTask)
- created_at

### Alert

最小字段：

- alert_id (PK)
- level: P0 / P1 / P2 / P3
- message
- source（risk / data / agent / system）
- status: open / acknowledged / suppressed
- entity_type (nullable)
- entity_id (nullable)
- created_at
- acknowledged_at (nullable)
- acknowledged_by (nullable)

### AlertAcknowledgment

最小字段：

- id (PK)
- alert_id (FK)
- user_id
- acknowledged_at
- note

数据保留策略：

- ChatMessage 消息内容：保留 90 天，到期后 `content` 字段清空（置为 "[已过期]"），其余元数据（message_id、session_id、role、tool_call_id、agent_task_id、created_at）永久保留以支撑审计追踪
- ChatMessage 中关联审计的记录（包含 tool_call、tool_result、审批决策的消息）：`content` 字段不清空，永久保留（与 PRD 审计要求对齐）
- ChatSession：保留 1 年
- Alert + AlertAcknowledgment：保留 1 年

## 29.5.11 UI 层降级策略

| 故障场景 | UI 行为 | 后端行为 |
|---------|---------|---------|
| WebSocket 断连 | 显示"数据可能陈旧"警告，自动降级 REST 轮询（30s） | Bridge 标记 unhealthy |
| Bridge 组件故障 | 前端检测无推送超过 90s，触发 REST 轮询降级 | Section 28 告警 |
| Redis 不可用 | 同上（PipelineBus 停止推送） | 参见 Section 23.5 |
| SSE 断流 | 显示"AI 响应中断"，提供重试按钮 | 服务端保持 session 5min |
| FastAPI 不可用 | 显示"系统维护中"，缓存最后已知数据 | Nginx 返回 502 |
| LLM API 不可用 | Chat 显示"AI 服务暂时不可用"，非 Chat 功能不受影响 | 503 + 重试 |
| Live 环境本地模型不可用 | Chat 显示"本地模型不可用，请检查 Ollama 服务状态。实盘数据不允许发送到外部服务。"，**禁止回退到云模型**，通知管理员 | 检测本地模型健康状态，返回 503 + 明确错误消息，不转发到第三方 API |

安全关键操作（Kill Switch / Force Flatten）不依赖实时通道，始终通过 REST POST 执行。

## 29.5.12 容量与扩展

### 容量目标（V1.5）

- 并发 WebSocket 连接：50（量化团队内部使用）
- 并发 SSE 流：20
- 单连接推送速率：≤ 10 msg/s
- PipelineBus → WebSocket Bridge 延迟：≤ 500ms

### 速率限制

- WebSocket 客户端→服务端：≤ 10 msg/min per connection（超出断连）
- SSE：每用户同时 ≤ 3 个活跃流
- Chat Messages：每用户 ≤ 20 msg/min，每 session ≤ 60 msg/hour
- REST API：只读 100 req/min，交易操作 10 req/min，回测启动 5 req/min
- **紧急操作（独立限流桶）：Kill Switch 激活 1 req/min（60s 冷却），Kill Switch 停用 1 req/5min，Force Flatten 3 req/min**
- 所有超限返回 429 或 force_disconnect

### 水平扩展（V2.0 规划）

- WebSocket：每个 FastAPI 实例维护本地连接表，Bridge 通过 Redis pub/sub 广播，无需 sticky session
- SSE：Chat Session 绑定创建实例，需 sticky session 或 session 状态存 Redis
- V1.5 单实例部署，不涉及上述复杂性

## 29.5.13 Chat 上下文管理策略

1. 系统提示（不可截断）：角色定义、安全约束、当前环境信息
2. 工具结果（可摘要）：超过 10 条的工具结果自动压缩为摘要
3. 用户消息（可截断）：最早的用户消息优先截断
4. 上下文注入：每次请求注入当前环境（Live/Paper）、用户角色、时间戳
5. 禁止在上下文中缓存仓位/订单数据，每次通过工具查询实时数据
6. Live 环境的 Chat 仅允许使用本地模型，Research/Backtest 环境可使用第三方模型（脱敏后）

## 29.5.14 UI API 错误分类

| 错误码 | 场景 | HTTP/WS 状态 |
|--------|------|-------------|
| WS_AUTH_FAILED | token 无效或过期 | 4001 (WS close) |
| WS_RATE_LIMITED | 客户端消息速率超限 | 4002 (WS close) |
| CHAT_SESSION_NOT_FOUND | session ID 不存在 | 404 |
| CHAT_LLM_UNAVAILABLE | LLM provider 不可用 | 503 |
| CHAT_LOCAL_MODEL_UNAVAILABLE | Live 环境本地模型不可用，禁止回退到云模型 | 503 + "实盘数据不允许发送到外部服务" |
| CHAT_CONTEXT_EXCEEDED | 对话上下文超限 | 400 |
| ALERT_ALREADY_ACK | alert 已被确认 | 409 |
| ACCOUNT_DATA_STALE | 账户数据无法刷新 | 200 + warning header |
| CONCURRENT_MODIFICATION | 实体被其他用户修改 | 409 |

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
8. WebSocket 实时推送端点（FR-API-001）
9. Web Dashboard 核心面板（Overview + Positions + Orders + Risk）
10. AI 对话界面基础版（Chat Session + LLM Adapter + Tool Executor）
11. Dashboard 与 AI Chat 联动
12. 回测结果可视化（收益曲线、回撤曲线、指标卡片）

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
|用户界面|无|增加第 11 层用户界面层（Web Dashboard + AI Chat），定义 WebSocket 推送、SSE 对话流、前后端架构分层|

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
8. `force_flatten` 是风控动作，不依赖策略二次确认
9. Paper → Live 必须有结构化准入框架
10. 恢复后默认 `pause_open`，不得自动冒进恢复
11. Hermes Agent 不得进入实盘下单主路径
12. Agent 只能通过 Tool Gateway 和 Proposal / Approval / ControlledExecution 闭环作用系统
13. Agent 输出不是事实源，不能替代交易数据库、审计系统和状态机
14. Agent 超时、失败、越权或上下文不完整时，Live 相关动作默认 fail-closed
15. 用户界面层是后端 API 的纯消费者，不承载业务逻辑、风控裁决或交易决策
16. Dashboard 与 AI Chat 共享同一套 REST API / WebSocket，不创建独立数据通道
17. AI Chat 中的 LLM 选择不影响后端 Agent 治理链，Policy Engine 校验与前端无关
18. 前端权限隐藏仅为 UX 优化，安全边界由后端 API 层强制执行
19. Live 环境 AI Chat 仅允许本地模型，本地模型不可用时禁止回退到云模型，避免实盘数据泄露
20. Kill Switch / Force Flatten 始终通过 REST POST 执行，不依赖 WebSocket，确保紧急操作可靠性