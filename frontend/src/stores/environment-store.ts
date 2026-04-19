import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Environment = 'research' | 'backtest' | 'paper' | 'live'

interface EnvironmentState {
  currentEnv: Environment
  setEnvironment: (env: Environment) => void
}

export const useEnvironmentStore = create<EnvironmentState>()(
  persist(
    (set) => ({
      currentEnv: 'research',
      setEnvironment: (env: Environment) => set({ currentEnv: env }),
    }),
    { name: 'hqmts-environment' },
  ),
)
