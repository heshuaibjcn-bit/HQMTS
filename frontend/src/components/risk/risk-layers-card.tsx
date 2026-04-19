import { useRiskStatus, type RiskStatus } from '@/hooks/use-risk'

const layerLabels: Record<string, string> = {
  pre_trade: '盘前检查',
  position: '持仓风控',
  portfolio: '组合风控',
  capital: '资金风控',
  compliance: '合规风控',
}

function statusColor(status: string) {
  if (status === 'pass') return 'text-[var(--color-success)]'
  if (status === 'warn') return 'text-[var(--color-warning)]'
  return 'text-[var(--color-danger)]'
}

function statusIcon(status: string) {
  if (status === 'pass') return '●'
  if (status === 'warn') return '◐'
  return '●'
}

export function RiskLayersCard() {
  const { data, isLoading } = useRiskStatus()

  if (isLoading) {
    return (
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <p className="text-sm text-[var(--color-text-muted)]">加载中...</p>
      </div>
    )
  }

  const layers = data?.layers as RiskStatus['layers'] | undefined

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <h3 className="text-sm font-medium text-[var(--color-text)]">五层风控状态</h3>
      <div className="mt-3 space-y-2">
        {Object.entries(layerLabels).map(([key, label]) => {
          const layer = layers?.[key as keyof RiskStatus['layers']]
          return (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-[var(--color-text-secondary)]">{label}</span>
              <div className="flex items-center gap-2">
                {layer && (
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {layer.checks_passed}/{layer.checks_total}
                  </span>
                )}
                <span className={statusColor(layer?.status ?? 'fail')}>
                  {statusIcon(layer?.status ?? 'fail')}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
