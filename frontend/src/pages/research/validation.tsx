import { useState } from 'react'
import { useAdmissions, useCreateAdmission, useEvaluateReadiness, useApproveAdmission } from '@/hooks/use-validation'
import { useAuthStore } from '@/stores/auth-store'
import { useNotificationStore } from '@/stores/notification-store'
import { LifecycleBreadcrumb } from '@/components/shared/lifecycle-breadcrumb'
import { Plus, Play, CheckCircle, XCircle, Clock, AlertCircle, RefreshCw, Rocket } from 'lucide-react'

const statusLabels: Record<string, { label: string; color: string }> = {
  pending_metrics: { label: '待收集指标', color: 'bg-yellow-100 text-yellow-700' },
  metrics_collected: { label: '已收集指标', color: 'bg-blue-100 text-blue-700' },
  pending_review: { label: '待审批', color: 'bg-orange-100 text-orange-700' },
  approved: { label: '已批准', color: 'bg-green-100 text-green-700' },
  rejected: { label: '已拒绝', color: 'bg-red-100 text-red-700' },
}

function StatusBadge({ status }: { status: string }) {
  const s = statusLabels[status] ?? { label: status, color: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${s.color}`}>{s.label}</span>
  )
}

export function ValidationPage() {
  const { data: admissions, isLoading, isError, refetch } = useAdmissions()
  const createAdmission = useCreateAdmission()
  const evaluateReadiness = useEvaluateReadiness()
  const approveAdmission = useApproveAdmission()

  const [showCreate, setShowCreate] = useState(false)
  const [newInstanceId, setNewInstanceId] = useState('')
  const [newVersion, setNewVersion] = useState('')
  const [approveDialog, setApproveDialog] = useState<{ id: string; decision: 'approved' | 'rejected' } | null>(null)
  const [approveReason, setApproveReason] = useState('')

  const toast = useNotificationStore.getState().addNotification

  const handleCreate = async () => {
    if (!newInstanceId.trim()) return
    try {
      await createAdmission.mutateAsync({ strategy_instance_id: newInstanceId, strategy_version: newVersion })
      setShowCreate(false)
      setNewInstanceId('')
      setNewVersion('')
    } catch (err) {
      console.error('创建验证失败:', err)
      toast('error', '创建验证失败，请稍后重试')
    }
  }

  const handleApprove = async (reason: string) => {
    if (!approveDialog) return
    const user = useAuthStore.getState().user
    if (!user) {
      toast('error', '请重新登录')
      return
    }
    try {
      await approveAdmission.mutateAsync({
        admission_id: approveDialog.id,
        approver: user.user_id ?? user.username,
        decision: approveDialog.decision,
        reason,
      })
      setApproveDialog(null)
      setApproveReason('')
    } catch (err) {
      console.error('审批操作失败:', err)
      toast('error', '审批操作失败，请稍后重试')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[var(--color-text)]">策略验证</h1>
        <div className="flex items-center gap-3">
          <LifecycleBreadcrumb currentStage="validate" />
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            创建验证
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
          <h3 className="text-sm font-medium text-[var(--color-text)]">新建准入验证</h3>
          <div className="mt-3 flex gap-3">
            <input
              value={newInstanceId}
              onChange={(e) => setNewInstanceId(e.target.value)}
              placeholder="策略实例 ID"
              className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3 py-1.5 text-sm"
            />
            <input
              value={newVersion}
              onChange={(e) => setNewVersion(e.target.value)}
              placeholder="版本号 (可选)"
              className="w-40 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3 py-1.5 text-sm"
            />
            <button onClick={handleCreate} disabled={createAdmission.isPending} className="rounded-md bg-[var(--color-primary)] px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50">
              提交
            </button>
            <button onClick={() => setShowCreate(false)} className="rounded-md px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]">
              取消
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">加载中...</div>
      ) : isError ? (
        <div className="flex flex-col items-center gap-3 py-8">
          <AlertCircle className="h-8 w-8 text-[var(--color-danger)]" />
          <p className="text-sm text-[var(--color-danger)]">加载验证记录失败</p>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1 rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            <RefreshCw className="h-3 w-3" />
            重试
          </button>
        </div>
      ) : (admissions ?? []).length === 0 ? (
        <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">
          暂无验证记录。点击 "创建验证" 开始 Paper-to-Live 准入流程。
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">策略实例</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">版本</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">状态</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">夏普比</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">交易天数</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">就绪度</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">操作</th>
              </tr>
            </thead>
            <tbody>
              {(admissions ?? []).map((a) => (
                <tr key={a.admission_id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]">
                  <td className="px-3 py-2 font-medium">{a.strategy_instance_id}</td>
                  <td className="px-3 py-2 text-[var(--color-text-muted)]">{a.strategy_version || '--'}</td>
                  <td className="px-3 py-2"><StatusBadge status={a.status} /></td>
                  <td className="px-3 py-2">{a.paper_sharpe_ratio?.toFixed(2) ?? '--'}</td>
                  <td className="px-3 py-2">{a.paper_trading_days ?? '--'}</td>
                  <td className="px-3 py-2">
                    {a.readiness_score != null ? (
                      <span className={a.readiness_passed ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'}>
                        {Math.round(a.readiness_score * 100)}%
                      </span>
                    ) : '--'}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-2">
                      {a.status === 'metrics_collected' && (
                        <button
                          onClick={() => evaluateReadiness.mutate(a.admission_id)}
                          disabled={evaluateReadiness.isPending}
                          className="flex items-center gap-1 text-xs text-[var(--color-primary)] hover:underline disabled:opacity-50"
                        >
                          <Play className="h-3 w-3" />
                          评估
                        </button>
                      )}
                      {a.status === 'pending_review' && (
                        <>
                          <button
                            onClick={() => setApproveDialog({ id: a.admission_id, decision: 'approved' })}
                            className="flex items-center gap-1 text-xs text-[var(--color-success)] hover:underline"
                          >
                            <CheckCircle className="h-3 w-3" />
                            批准
                          </button>
                          <button
                            onClick={() => setApproveDialog({ id: a.admission_id, decision: 'rejected' })}
                            className="flex items-center gap-1 text-xs text-[var(--color-danger)] hover:underline"
                          >
                            <XCircle className="h-3 w-3" />
                            拒绝
                          </button>
                        </>
                      )}
                      {a.status === 'pending_metrics' && (
                        <span className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
                          <Clock className="h-3 w-3" />
                          等待指标
                        </span>
                      )}
                      {a.status === 'approved' && (
                        <button
                          disabled
                          title="后端接口开发中"
                          className="flex items-center gap-1 text-xs text-[var(--color-text-muted)] opacity-40 cursor-not-allowed"
                        >
                          <Rocket className="h-3 w-3" />
                          启动模拟
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Approval dialog */}
      {approveDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={(e) => { if (e.target === e.currentTarget) setApproveDialog(null) }}>
          <div className="w-full max-w-sm rounded-lg bg-[var(--color-bg)] p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">
              {approveDialog.decision === 'approved' ? '批准上线' : '拒绝上线'}
            </h2>
            <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
              {approveDialog.decision === 'approved'
                ? '确认批准该策略从模拟转为实盘交易？'
                : '确认拒绝该策略的上线申请？'}
            </p>
            <div className="mt-3">
              <label className="text-sm text-[var(--color-text-secondary)]">
                审批原因{approveDialog.decision === 'rejected' && <span className="text-[var(--color-danger)]"> *</span>}
              </label>
              <textarea
                value={approveReason}
                onChange={(e) => setApproveReason(e.target.value)}
                placeholder={approveDialog.decision === 'approved' ? '批准原因 (可选)' : '请说明拒绝原因'}
                rows={3}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3 py-1.5 text-sm resize-none"
              />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => { setApproveDialog(null); setApproveReason('') }}
                className="rounded-md px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]"
              >
                取消
              </button>
              <button
                onClick={() => handleApprove(approveReason)}
                disabled={approveAdmission.isPending || (approveDialog.decision === 'rejected' && !approveReason.trim())}
                className={`rounded-md px-4 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-40 ${
                  approveDialog.decision === 'approved' ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'
                }`}
              >
                确认{approveDialog.decision === 'approved' ? '批准' : '拒绝'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
