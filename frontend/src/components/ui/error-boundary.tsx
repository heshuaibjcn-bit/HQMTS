import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="flex min-h-[200px] items-center justify-center p-8">
          <div className="text-center">
            <h2 className="text-lg font-semibold text-[var(--color-danger)]">页面出错</h2>
            <p className="mt-2 text-sm text-[var(--color-text-muted)]">
              {this.state.error?.message || '未知错误'}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="mt-4 rounded-md bg-[var(--color-bg-tertiary)] px-4 py-2 text-sm hover:opacity-80"
            >
              重试
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
