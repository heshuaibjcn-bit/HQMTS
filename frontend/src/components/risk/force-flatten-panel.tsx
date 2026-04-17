import { useState } from 'react'
import { apiClient } from '@/lib/api-client'
import { useQuery } from '@tanstack/react-query'
import { ConfirmActionDialog } from './confirm-action-dialog'
import { AlertTriangle, Loader2 } from 'lucide-react'

interface FlattenProgress {
  flatten_id: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  total_positions: number
  flattened: number
  failed: number
}

export function ForceFlattenPanel() {
  const [confirming, setConfirming] = useState(false)
  const [flattenId, setFlattenId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: progress } = useQuery<FlattenProgress>({
    queryKey: ['risk', 'flatten', flattenId],
    queryFn: () => apiClient.get(`/risk/flatten/${flattenId}`),
    enabled: !!flattenId,
    refetchInterval: (q) => {
      if (q.state.data?.status === 'completed' || q.state.data?.status === 'failed') return false
      return 2000
    },
  })

  const handleConfirm = async () => {
    setLoading(true)
    setConfirming(false)
    setError(null)
    try {
      const result = await apiClient.post<{ flatten_id: string }>('/risk/flatten')
      if (result) {
        setFlattenId(result.flatten_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Force flatten failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <h3 className="text-sm font-medium text-[var(--color-text)]">Force Flatten</h3>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">
          强制平仓所有持仓。此操作不可逆。
        </p>

        {error && (
          <div className="mt-3 rounded border border-[var(--color-danger)] bg-red-50 p-2 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        {progress && progress.status !== 'completed' && progress.status !== 'failed' && (
          <div className="mt-3 rounded border border-[var(--color-warning)] bg-amber-50 p-2">
            <div className="flex items-center gap-2 text-sm">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--color-warning)]" />
              <span>
                平仓进度: {progress.flattened}/{progress.total_positions}
              </span>
            </div>
          </div>
        )}

        {progress?.status === 'completed' && (
          <div className="mt-3 rounded border border-[var(--color-success)] bg-green-50 p-2 text-sm text-[var(--color-success)]">
            平仓完成: {progress.flattened} 笔成功, {progress.failed} 笔失败
          </div>
        )}

        {progress?.status === 'failed' && (
          <div className="mt-3 rounded border border-[var(--color-danger)] bg-red-50 p-2 text-sm text-[var(--color-danger)]">
            平仓失败
          </div>
        )}

        <button
          onClick={() => setConfirming(true)}
          disabled={loading || (progress?.status === 'in_progress')}
          className="mt-3 flex items-center gap-1 rounded-md border border-[var(--color-danger)] px-3 py-1.5 text-sm text-[var(--color-danger)] hover:bg-red-50 disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <AlertTriangle className="h-3.5 w-3.5" />
          )}
          触发强制平仓
        </button>
      </div>
      {confirming && (
        <ConfirmActionDialog
          title="强制平仓确认"
          message="确认触发 Force Flatten？所有持仓将以市价卖出。此操作不可逆，需等待服务端确认。"
          confirmLabel="确认强制平仓"
          onConfirm={handleConfirm}
          onClose={() => setConfirming(false)}
        />
      )}
    </>
  )
}
