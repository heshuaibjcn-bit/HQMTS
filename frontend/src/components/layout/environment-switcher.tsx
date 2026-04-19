import { useEnvironmentStore } from '@/stores/environment-store'
import { useSidebarStore, type SidebarSection } from '@/stores/sidebar-store'

type Environment = 'research' | 'backtest' | 'paper' | 'live'

const environments: { value: Environment; label: string }[] = [
  { value: 'research', label: 'Research' },
  { value: 'backtest', label: 'Backtest' },
  { value: 'paper', label: 'Paper' },
  { value: 'live', label: 'Live' },
]

const ENV_SECTION_MAP: Record<Environment, SidebarSection> = {
  research: 'research',
  backtest: 'research',
  paper: 'trading',
  live: 'trading',
}

export function EnvironmentSwitcher() {
  const currentEnv = useEnvironmentStore((s) => s.currentEnv)
  const setEnvironment = useEnvironmentStore((s) => s.setEnvironment)
  const collapseOthers = useSidebarStore((s) => s.collapseOthers)

  const handleSwitch = (env: Environment) => {
    setEnvironment(env)
    collapseOthers(ENV_SECTION_MAP[env])
  }

  return (
    <div className="flex gap-1 rounded-md bg-[var(--color-bg-tertiary)] p-1">
      {environments.map((env) => (
        <button
          key={env.value}
          onClick={() => handleSwitch(env.value)}
          className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
            currentEnv === env.value
              ? env.value === 'live'
                ? 'bg-red-500 text-white'
                : 'bg-[var(--color-bg)] text-[var(--color-text)] shadow-sm'
              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
          }`}
        >
          {env.label}
        </button>
      ))}
    </div>
  )
}
