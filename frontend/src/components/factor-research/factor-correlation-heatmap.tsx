import { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'

interface FactorCorrelationHeatmapProps {
  matrix: (number | null)[][]
  factors: string[]
  height?: string
}

export function FactorCorrelationHeatmap({
  matrix,
  factors,
  height = '400px',
}: FactorCorrelationHeatmapProps) {
  const option = useMemo(() => {
    if (factors.length === 0 || matrix.length === 0) {
      return {
        title: { text: '无相关性数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } },
      }
    }

    const data: [number, number, number | string][] = []
    for (let i = 0; i < matrix.length; i++) {
      for (let j = 0; j < matrix[i].length; j++) {
        const v = matrix[i][j]
        data.push([j, i, v === null ? '-' : v])
      }
    }

    return {
      tooltip: {
        formatter: (params: { data: (string | number)[] }) => {
          const [x, y, val] = params.data
          return `${factors[x as number]} vs ${factors[y as number]}<br/>相关系数: ${typeof val === 'number' ? val.toFixed(4) : val}`
        },
      },
      grid: { left: 100, right: 40, top: 10, bottom: 80 },
      xAxis: {
        type: 'category' as const,
        data: factors,
        splitArea: { show: true },
        axisLabel: { fontSize: 10, color: '#999', rotate: 30 },
      },
      yAxis: {
        type: 'category' as const,
        data: factors,
        splitArea: { show: true },
        axisLabel: { fontSize: 10, color: '#999' },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: {
          color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
        },
        textStyle: { fontSize: 10, color: '#999' },
      },
      series: [{
        type: 'heatmap',
        data,
        label: {
          show: factors.length <= 10,
          fontSize: 9,
          formatter: (params: { data: (string | number)[] }) => {
            const val = params.data[2]
            return typeof val === 'number' ? val.toFixed(2) : ''
          },
        },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
      }],
    }
  }, [matrix, factors])

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
      <ReactECharts option={option} style={{ height }} notMerge />
    </div>
  )
}
