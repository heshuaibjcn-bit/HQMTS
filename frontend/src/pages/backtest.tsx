import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface BacktestResult {
  backtest_id: string
  strategy_name: string
  strategy_version: string
  instruments: string[]
  cycle: string
  start_date: string
  end_date: string
  initial_cash: string
  final_total_asset: string
  total_return: string
  annualized_return: string
  max_drawdown: string
  sharpe_ratio: string
  total_trades: number
  win_rate: string
  profit_factor: string
  created_at: string
}

function formatPercent(value: string) {
  const num = parseFloat(value)
  if (isNaN(num)) return '--'
  return `${(num * 100).toFixed(2)}%`
}

export function BacktestPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['backtest', 'results'],
    queryFn: async () => {
      const results = await apiClient.get<BacktestResult[]>('/backtest/')
      return results ?? []
    },
  })

  const results = data ?? []

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">回测与验证</h1>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">回测结果</h2>
        {isLoading ? (
          <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">加载中...</div>
        ) : results.length === 0 ? (
          <div className="py-8 text-center text-sm text-[var(--color-text-muted)]">暂无回测结果</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">策略</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">标的</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">周期</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">总收益</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">最大回撤</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">夏普比</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">胜率</th>
                  <th className="px-3 py-2 text-left font-medium text-[var(--color-text-secondary)]">交易次数</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.backtest_id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]">
                    <td className="px-3 py-2 font-medium">
                      <div>{r.strategy_name}</div>
                      <div className="text-xs text-[var(--color-text-muted)]">{r.strategy_version}</div>
                    </td>
                    <td className="px-3 py-2">{r.instruments.join(', ')}</td>
                    <td className="px-3 py-2">{r.cycle}</td>
                    <td className="px-3 py-2">
                      <span className={parseFloat(r.total_return) >= 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'}>
                        {formatPercent(r.total_return)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-[var(--color-danger)]">{formatPercent(r.max_drawdown)}</td>
                    <td className="px-3 py-2">{parseFloat(r.sharpe_ratio).toFixed(2)}</td>
                    <td className="px-3 py-2">{formatPercent(r.win_rate)}</td>
                    <td className="px-3 py-2">{r.total_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
