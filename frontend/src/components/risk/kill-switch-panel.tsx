import { useState } from 'react'
import { useRiskStatus, useActivateKillSwitch, useDeactivateKillSwitch } from '@/hooks/use-risk'
import { Power, PowerOff } from 'lucide-react'

const CONFIRM_PHRASE = 'KILL SWITCH'

export function KillSwitchPanel() {
  const { data } = useRiskStatus()
  const activate = useActivateKillSwitch()
  const deactivate = useDeactivateKillSwitch()
  const [confirmAction, setConfirmAction] = useState<'activate' | 'deactivate' | null>(null)
  const [typed, setTyped] = useState('')

  const isActive = data?.kill_switch_active ?? false
  const canConfirm = typed === CONFIRM_PHRASE

  const handleConfirm = async () => {
    if (!canConfirm) return
    if (confirmAction === 'activate') {
      await activate.mutateAsync()
    } else {
      await deactivate.mutateAsync()
    }
    setConfirmAction(null)
    setTyped('')
  }

  return (
    <>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <h3 className="text-sm font-medium text-[var(--color-text)]">Kill Switch</h3>
        <div className="mt-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isActive ? 'bg-[var(--color-danger)]' : 'bg-[var(--color-success)]'
              }`}
            />
            <span className="text-sm text-[var(--color-text-secondary)]">
              {isActive ? '已激活 (所有交易已停止)' : '未激活'}
            </span>
          </div>
          {isActive ? (
            <button
              onClick={() => { setConfirmAction('deactivate'); setTyped('') }}
              disabled={deactivate.isPending}
              className="flex items-center gap-1 rounded-md bg-[var(--color-success)] px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              <Power className="h-3.5 w-3.5" />
              停用
            </button>
          ) : (
            <button
              onClick={() => { setConfirmAction('activate'); setTyped('') }}
              disabled={activate.isPending}
              className="flex items-center gap-1 rounded-md bg-[var(--color-danger)] px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-50"
            >
              <PowerOff className="h-3.5 w-3.5" />
              激活
            </button>
          )}
        </div>
      </div>
      {confirmAction && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => { if (e.target === e.currentTarget) { setConfirmAction(null); setTyped('') } }}
        >
          <div className="w-full max-w-sm rounded-lg bg-[var(--color-bg)] p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">
              {confirmAction === 'activate' ? '激活 Kill Switch' : '停用 Kill Switch'}
            </h2>
            <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
              {confirmAction === 'activate'
                ? '确认激活 Kill Switch？所有交易将立即停止。'
                : '确认停用 Kill Switch？交易将恢复。'}
            </p>
            <p className="mt-3 text-xs text-[var(--color-danger)]">
              请输入 <strong>{CONFIRM_PHRASE}</strong> 以确认操作:
            </p>
            <input
              type="text"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3 py-2 text-sm font-mono"
              placeholder={CONFIRM_PHRASE}
              autoComplete="off"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => { setConfirmAction(null); setTyped('') }}
                className="rounded-md px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]"
              >
                取消
              </button>
              <button
                onClick={handleConfirm}
                disabled={!canConfirm}
                className="rounded-md bg-[var(--color-danger)] px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-30"
              >
                {confirmAction === 'activate' ? '确认激活' : '确认停用'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
