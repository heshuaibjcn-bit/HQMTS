import { useEnvironmentStore } from '@/stores/environment-store'

export function ModelProviderBadge() {
  const env = useEnvironmentStore((s) => s.currentEnv)

  const isLive = env === 'live'
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-medium ${
        isLive ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
      }`}
    >
      {isLive ? 'Ollama' : 'OpenAI / Ollama'}
    </span>
  )
}
