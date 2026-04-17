import type { Approval } from '@/hooks/use-approvals'
import { ApprovalDialog } from './approval-dialog'
import { useState } from 'react'
import { ShieldCheck, Clock } from 'lucide-react'
import { formatTime } from '@/lib/utils'

interface Props {
  approval: Approval
}

export function ApprovalCard({ approval }: Props) {
  const [showDialog, setShowDialog] = useState(false)
  const [action, setAction] = useState<'approve' | 'reject'>('approve')

  const isPending = approval.status === 'pending'

  const statusColors: Record<string, string> = {
    pending: 'border-amber-300 bg-amber-50',
    approved: 'border-green-300 bg-green-50',
    rejected: 'border-red-300 bg-red-50',
    expired: 'border-gray-300 bg-gray-50',
  }

  const statusLabels: Record<string, string> = {
    pending: '待审批',
    approved: '已通过',
    rejected: '已拒绝',
    expired: '已过期',
  }

  return (
    <>
      <div
        className={`rounded-lg border p-3 ${statusColors[approval.status] ?? 'border-gray-300 bg-gray-50'}`}
      >
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-[var(--color-text-secondary)]" />
          <span className="text-sm font-medium text-[var(--color-text)]">
            审批请求
          </span>
          <span className="text-xs text-[var(--color-text-muted)]">
            {statusLabels[approval.status]}
          </span>
        </div>
        <p className="mt-1 text-sm font-medium text-[var(--color-text)]">
          {approval.title}
        </p>
        <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
          {approval.description}
        </p>
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
            <Clock className="h-3 w-3" />
            <span>{formatTime(approval.created_at)}</span>
            <span className="ml-1">风险: {approval.risk_level}</span>
          </div>
          {isPending && approval.actions.approve && (
            <div className="flex gap-1">
              <button
                onClick={() => {
                  setAction('approve')
                  setShowDialog(true)
                }}
                className="rounded bg-[var(--color-success)] px-2 py-0.5 text-xs text-white hover:opacity-90"
              >
                通过
              </button>
              {approval.actions.reject && (
                <button
                  onClick={() => {
                    setAction('reject')
                    setShowDialog(true)
                  }}
                  className="rounded bg-[var(--color-danger)] px-2 py-0.5 text-xs text-white hover:opacity-90"
                >
                  拒绝
                </button>
              )}
            </div>
          )}
        </div>
      </div>
      {showDialog && (
        <ApprovalDialog
          approval={approval}
          action={action}
          onClose={() => setShowDialog(false)}
        />
      )}
    </>
  )
}
