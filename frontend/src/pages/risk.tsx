import { RiskLayersCard } from '@/components/risk/risk-layers-card'
import { KillSwitchPanel } from '@/components/risk/kill-switch-panel'
import { ForceFlattenPanel } from '@/components/risk/force-flatten-panel'

export function RiskPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">风控</h1>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RiskLayersCard />
        <KillSwitchPanel />
      </div>
      <ForceFlattenPanel />
    </div>
  )
}
