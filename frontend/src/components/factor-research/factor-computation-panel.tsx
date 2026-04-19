import { useState, useCallback, useEffect } from 'react'
import { useFactors, useComputeFactors, useCorrelationMatrix } from '@/hooks/use-factor-research'
import { FactorChart } from './factor-chart'
import { FactorCorrelationHeatmap } from './factor-correlation-heatmap'
import { Loader2 } from 'lucide-react'
import type { ResearchContext } from '@/pages/research/factor-research'

const CYCLES = [
  { value: '1m', label: '1分钟' },
  { value: '5m', label: '5分钟' },
  { value: '15m', label: '15分钟' },
  { value: '30m', label: '30分钟' },
  { value: '1h', label: '1小时' },
  { value: '1d', label: '日线' },
]

function getDefaultDateRange() {
  const end = new Date()
  const start = new Date()
  start.setFullYear(start.getFullYear() - 1)
  return {
    startDate: start.toISOString().slice(0, 10),
    endDate: end.toISOString().slice(0, 10),
  }
}

interface FactorComputationPanelProps {
  onContextChange?: (ctx: ResearchContext) => void
}

export function FactorComputationPanel({ onContextChange }: FactorComputationPanelProps) {
  const { data: factors } = useFactors()
  const defaultRange = getDefaultDateRange()

  const [instrumentIds, setInstrumentIds] = useState('')
  const [selectedFactors, setSelectedFactors] = useState<string[]>([])
  const [cycle, setCycle] = useState('1d')
  const [startDate, setStartDate] = useState(defaultRange.startDate)
  const [endDate, setEndDate] = useState(defaultRange.endDate)
  const [chartType, setChartType] = useState<'line' | 'scatter' | 'heatmap'>('line')

  const computeMutation = useComputeFactors()
  const correlationMutation = useCorrelationMatrix()

  // Broadcast context to AI research tab
  useEffect(() => {
    const instruments = instrumentIds.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean)
    onContextChange?.({
      instruments,
      factors: selectedFactors,
      timeRange: startDate && endDate ? `${startDate} ~ ${endDate}` : '',
    })
  }, [instrumentIds, selectedFactors, startDate, endDate, onContextChange])

  const handleCompute = useCallback(() => {
    const ids = instrumentIds
      .split(/[,，\s]+/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (ids.length === 0 || selectedFactors.length === 0) return

    if (chartType === 'heatmap') {
      correlationMutation.mutate({
        instrument_id: ids[0],
        factor_names: selectedFactors,
        cycle,
        start_date: startDate,
        end_date: endDate,
      })
    } else {
      computeMutation.mutate({
        instrument_ids: ids,
        factor_names: selectedFactors,
        cycle,
        start_date: startDate,
        end_date: endDate,
      })
    }
  }, [instrumentIds, selectedFactors, cycle, startDate, endDate, chartType, computeMutation, correlationMutation])

  const toggleFactor = (name: string) => {
    setSelectedFactors((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    )
  }

  const isLoading = computeMutation.isPending || correlationMutation.isPending
  const computedValues = computeMutation.data?.values ?? []

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
      {/* Left: Control panel */}
      <div className="space-y-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
        <h3 className="text-sm font-medium text-[var(--color-text)]">因子计算</h3>

        {/* Instruments */}
        <div>
          <label className="mb-1 block text-xs text-[var(--color-text-secondary)]">
            标的代码 (逗号分隔)
          </label>
          <input
            type="text"
            placeholder="如: 000001.SZ, 600519.SH"
            value={instrumentIds}
            onChange={(e) => setInstrumentIds(e.target.value)}
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
          />
        </div>

        {/* Cycle */}
        <div>
          <label className="mb-1 block text-xs text-[var(--color-text-secondary)]">周期</label>
          <select
            value={cycle}
            onChange={(e) => setCycle(e.target.value)}
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-sm text-[var(--color-text)] outline-none"
          >
            {CYCLES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>

        {/* Date range */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="mb-1 block text-xs text-[var(--color-text-secondary)]">开始日期</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1.5 text-xs text-[var(--color-text)] outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--color-text-secondary)]">结束日期</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1.5 text-xs text-[var(--color-text)] outline-none"
            />
          </div>
        </div>

        {/* Factor selection */}
        <div>
          <label className="mb-1 block text-xs text-[var(--color-text-secondary)]">
            选择因子 ({selectedFactors.length})
          </label>
          <div className="max-h-48 overflow-y-auto space-y-1 rounded border border-[var(--color-border)] p-2">
            {(factors ?? []).map((f) => (
              <label key={f.name} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={selectedFactors.includes(f.name)}
                  onChange={() => toggleFactor(f.name)}
                  className="rounded border-[var(--color-border)]"
                />
                <span className="font-mono text-[var(--color-text)]">{f.name}</span>
                <span className="text-[var(--color-text-muted)]">{f.description}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Chart type */}
        <div>
          <label className="mb-1 block text-xs text-[var(--color-text-secondary)]">图表类型</label>
          <div className="flex gap-1">
            {(['line', 'scatter', 'heatmap'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setChartType(t)}
                className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                  chartType === t
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                }`}
              >
                {t === 'line' ? '线图' : t === 'scatter' ? '散点' : '热力图'}
              </button>
            ))}
          </div>
        </div>

        {/* Compute button */}
        <button
          onClick={handleCompute}
          disabled={isLoading || !instrumentIds.trim() || selectedFactors.length === 0}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-[var(--color-primary)] px-3 py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:opacity-50"
        >
          {isLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {isLoading ? '计算中...' : '计算'}
        </button>
      </div>

      {/* Right: Chart */}
      <div>
        {chartType === 'heatmap' ? (
          correlationMutation.data ? (
            <FactorCorrelationHeatmap
              matrix={correlationMutation.data.matrix}
              factors={correlationMutation.data.factors}
            />
          ) : (
            <div className="flex h-[360px] items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm text-[var(--color-text-muted)]">
              选择因子并点击计算查看相关性热力图
            </div>
          )
        ) : computedValues.length > 0 ? (
          <FactorChart values={computedValues} chartType={chartType} />
        ) : (
          <div className="flex h-[360px] items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm text-[var(--color-text-muted)]">
            选择标的和因子，点击计算查看图表
          </div>
        )}

        {(computeMutation.isError || correlationMutation.isError) && (
          <div className="mt-2 rounded bg-red-50 px-3 py-2 text-xs text-red-600">
            计算失败: {(computeMutation.error ?? correlationMutation.error)?.message}
          </div>
        )}
      </div>
    </div>
  )
}
