import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth-store'

export function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-secondary)]">
      <div className="w-full max-w-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-8 shadow-sm">
        <h1 className="mb-6 text-center text-xl font-semibold text-[var(--color-text)]">
          HQMTS 登录
        </h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-[var(--color-text-secondary)]">
              用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-md border border-[var(--color-border)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-[var(--color-text-secondary)]">
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-[var(--color-border)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]"
              required
            />
          </div>
          {error && (
            <p className="text-sm text-[var(--color-danger)]">{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
      </div>
    </div>
  )
}
