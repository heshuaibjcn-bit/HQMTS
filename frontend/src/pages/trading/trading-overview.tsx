import { AccountSummaryCard } from '@/components/overview/account-summary-card'
import { PnLCard } from '@/components/overview/pnl-card'
import { ActiveStrategiesCard } from '@/components/overview/active-strategies-card'
import { SystemHealthCard } from '@/components/overview/system-health-card'
import { RecentAlertsCard } from '@/components/overview/recent-alerts-card'

export function TradingOverviewPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">交易总览</h1>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <AccountSummaryCard />
              <PnLCard />
            </div>
          </div>
        </div>
        <RecentAlertsCard />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ActiveStrategiesCard />
        <SystemHealthCard />
      </div>
    </div>
  )
}
