import { X } from 'lucide-react'

interface Props {
  title: string
  message: string
  confirmLabel: string
  onConfirm: () => void
  onClose: () => void
  dismissible?: boolean
}

export function ConfirmActionDialog({ title, message, confirmLabel, onConfirm, onClose, dismissible = false }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={dismissible ? onClose : undefined}
    >
      <div
        className="w-full max-w-sm rounded-lg bg-[var(--color-bg)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">{title}</h2>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="mt-3 text-sm text-[var(--color-text-secondary)]">{message}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="rounded-md bg-[var(--color-danger)] px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
