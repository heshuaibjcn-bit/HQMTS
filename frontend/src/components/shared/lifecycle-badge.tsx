export type LifecycleStage = 'research' | 'backtest' | 'validate' | 'paper' | 'live'

const STAGES: Record<LifecycleStage, { label: string; color: string }> = {
  research: { label: '研究', color: 'bg-blue-100 text-blue-700' },
  backtest: { label: '回测', color: 'bg-indigo-100 text-indigo-700' },
  validate: { label: '验证', color: 'bg-yellow-100 text-yellow-700' },
  paper: { label: '模拟', color: 'bg-orange-100 text-orange-700' },
  live: { label: '实盘', color: 'bg-green-100 text-green-700' },
}

export function LifecycleBadge({ stage }: { stage: LifecycleStage }) {
  const s = STAGES[stage]
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${s.color}`}>
      {s.label}
    </span>
  )
}
