import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { FactorValue } from '@/hooks/use-factor-research'

interface FactorChartProps {
  values: FactorValue[]
  chartType?: 'line' | 'scatter'
  height?: string
}

const FACTOR_COLORS = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
  '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#48b8d0',
]

export function FactorChart({ values, chartType = 'line', height = '360px' }: FactorChartProps) {
  const option = useMemo(() => {
    if (values.length === 0) {
      return {
        title: { text: '无数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } },
        xAxis: { show: false },
        yAxis: { show: false },
        series: [],
      }
    }

    // Group by factor_name + instrument_id
    const groups: Record<string, FactorValue[]> = {}
    for (const v of values) {
      const key = `${v.factor_name} (${v.instrument_id})`
      if (!groups[key]) groups[key] = []
      groups[key].push(v)
    }

    const groupKeys = Object.keys(groups)

    if (chartType === 'line') {
      const allTimestamps = Array.from(new Set(values.map((v) => v.timestamp))).sort()
      const series = groupKeys.map((key, idx) => ({
        name: key,
        type: 'line' as const,
        data: allTimestamps.map((ts) => {
          const v = groups[key].find((fv) => fv.timestamp === ts)
          return v ? v.value : null
        }),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5 },
        itemStyle: { color: FACTOR_COLORS[idx % FACTOR_COLORS.length] },
      }))

      return {
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        legend: {
          type: 'scroll',
          bottom: 0,
          textStyle: { fontSize: 11, color: '#999' },
        },
        grid: { left: 60, right: 20, top: 20, bottom: 40 },
        xAxis: {
          type: 'category' as const,
          data: allTimestamps.map((ts) => {
            try {
              return new Date(ts).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
            } catch {
              return ts
            }
          }),
          axisLabel: { fontSize: 10, color: '#999' },
        },
        yAxis: {
          type: 'value' as const,
          axisLabel: { fontSize: 10, color: '#999' },
          splitLine: { lineStyle: { color: '#f0f0f0' } },
        },
        series,
        dataZoom: [
          { type: 'inside' as const, start: 0, end: 100 },
        ],
      }
    }

    // scatter: first two factor groups as x, y
    if (groupKeys.length >= 2) {
      const g1 = groups[groupKeys[0]]
      const g2 = groups[groupKeys[1]]
      const tsMap1 = new Map(g1.map((v) => [v.timestamp, v.value]))
      const tsMap2 = new Map(g2.map((v) => [v.timestamp, v.value]))
      const data: [number, number][] = []
      for (const [ts, v1] of tsMap1) {
        const v2 = tsMap2.get(ts)
        if (v2 !== undefined) data.push([v1, v2])
      }

      return {
        tooltip: {
          formatter: (params: { data: number[] }) =>
            `${groupKeys[0]}: ${params.data[0]?.toFixed(4)}<br/>${groupKeys[1]}: ${params.data[1]?.toFixed(4)}`,
        },
        grid: { left: 60, right: 20, top: 20, bottom: 40 },
        xAxis: {
          name: groupKeys[0],
          nameTextStyle: { fontSize: 11, color: '#999' },
          axisLabel: { fontSize: 10, color: '#999' },
        },
        yAxis: {
          name: groupKeys[1],
          nameTextStyle: { fontSize: 11, color: '#999' },
          axisLabel: { fontSize: 10, color: '#999' },
        },
        series: [{
          type: 'scatter',
          data,
          symbolSize: 4,
          itemStyle: { color: '#5470c6', opacity: 0.6 },
        }],
      }
    }

    // Fallback to line for single factor
    return {
      title: { text: '散点图需要至少2个因子', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } },
    }
  }, [values, chartType])

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
      <ReactECharts option={option} style={{ height }} notMerge />
    </div>
  )
}
