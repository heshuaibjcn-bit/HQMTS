import { Check } from 'lucide-react'
import type { LifecycleStage } from './lifecycle-badge'

const STAGE_ORDER: LifecycleStage[] = ['research', 'backtest', 'validate', 'paper', 'live']

const STAGE_LABELS: Record<LifecycleStage, string> = {
  research: '研究',
  backtest: '回测',
  validate: '验证',
  paper: '模拟',
  live: '实盘',
}

interface LifecycleBreadcrumbProps {
  currentStage: LifecycleStage
  className?: string
}

export function LifecycleBreadcrumb({ currentStage, className = '' }: LifecycleBreadcrumbProps) {
  const currentIndex = STAGE_ORDER.indexOf(currentStage)

  return (
    <div className={`flex items-center gap-1 ${className}`}>
      {STAGE_ORDER.map((stage, i) => {
        const isCompleted = i < currentIndex
        const isCurrent = i === currentIndex
        const isFuture = i > currentIndex

        return (
          <div key={stage} className="flex items-center">
            {i > 0 && (
              <div
                className={`h-px w-4 ${
                  i <= currentIndex ? 'bg-[var(--color-primary)]' : 'bg-[var(--color-border)]'
                }`}
              />
            )}
            <div className="flex flex-col items-center gap-0.5">
              <div
                className={`flex h-5 w-5 items-center justify-center rounded-full text-xs ${
                  isCompleted
                    ? 'bg-[var(--color-success)] text-white'
                    : isCurrent
                      ? 'bg-[var(--color-primary)] text-white animate-pulse'
                      : 'border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text-muted)]'
                }`}
              >
                {isCompleted ? <Check className="h-3 w-3" /> : i + 1}
              </div>
              <span
                className={`text-[10px] ${
                  isCompleted || isCurrent ? 'text-[var(--color-text)]' : 'text-[var(--color-text-muted)]'
                }`}
              >
                {STAGE_LABELS[stage]}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
