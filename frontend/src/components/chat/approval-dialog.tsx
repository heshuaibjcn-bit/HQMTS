import { useState } from 'react'
import type { Approval } from '@/hooks/use-approvals'
import { useApproveProposal, useRejectProposal } from '@/hooks/use-approvals'
import { X } from 'lucide-react'

interface Props {
  approval: Approval
  action: 'approve' | 'reject'
  onClose: () => void
}

export function ApprovalDialog({ approval, action, onClose }: Props) {
  const approve = useApproveProposal()
  const reject = useRejectProposal()
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)

  const isApprove = action === 'approve'

  const handleConfirm = async () => {
    setLoading(true)
    try {
      if (isApprove) {
        await approve.mutateAsync({ proposalId: approval.proposal_id, note })
      } else {
        await reject.mutateAsync({ proposalId: approval.proposal_id, reason: note || '拒绝' })
      }
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-lg bg-[var(--color-bg)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">
            {isApprove ? '确认通过' : '确认拒绝'}
          </h2>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
          {approval.title}
        </p>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">
          风险等级: {approval.risk_level} | 提交者: {approval.proposed_by}
        </p>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={isApprove ? '备注 (可选)' : '拒绝原因'}
          className="mt-3 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
          rows={3}
        />
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]"
          >
            取消
          </button>
          <button
            onClick={handleConfirm}
            disabled={loading || (!isApprove && !note.trim())}
            className={`rounded-md px-3 py-1.5 text-sm text-white disabled:opacity-50 ${
              isApprove
                ? 'bg-[var(--color-success)] hover:opacity-90'
                : 'bg-[var(--color-danger)] hover:opacity-90'
            }`}
          >
            {loading ? '处理中...' : isApprove ? '确认通过' : '确认拒绝'}
          </button>
        </div>
      </div>
    </div>
  )
}
