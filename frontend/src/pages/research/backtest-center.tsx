import { BacktestPage } from '../backtest'
import { LifecycleBreadcrumb } from '@/components/shared/lifecycle-breadcrumb'

export default function BacktestCenterPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[var(--color-text)]">回测中心</h1>
        <LifecycleBreadcrumb currentStage="backtest" />
      </div>
      <BacktestPage />
    </div>
  )
}
