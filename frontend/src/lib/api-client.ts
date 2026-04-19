const BASE_URL = ''

interface RequestOptions extends RequestInit {
  params?: Record<string, string>
}

class ApiClient {
  private refreshPromise: Promise<boolean> | null = null

  private getToken(): string | null {
    return useAuthStore.getState().token
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { params, ...fetchOptions } = options

    let url = `${BASE_URL}${path}`
    if (params) {
      const searchParams = new URLSearchParams(params)
      url += `?${searchParams.toString()}`
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    const token = this.getToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(url, {
      ...fetchOptions,
      headers,
    })

    if (response.status === 401) {
      // Singleton refresh: all concurrent 401s share one promise
      if (!this.refreshPromise) {
        this.refreshPromise = this.tryRefresh().finally(() => {
          this.refreshPromise = null
        })
      }
      const refreshed = await this.refreshPromise
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.getToken()}`
        const retryResponse = await fetch(url, { ...fetchOptions, headers })
        return retryResponse.json()
      }
      useAuthStore.getState().logout()
      throw new Error('Session expired')
    }

    if (response.status === 204) return undefined as T

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  async tryRefresh(): Promise<boolean> {
    const refreshToken = useAuthStore.getState().refreshToken
    if (!refreshToken) return false

    try {
      const response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!response.ok) return false

      const data = await response.json()
      useAuthStore.getState().setTokens(data.access_token, data.refresh_token)
      return true
    } catch {
      return false
    }
  }

  get<T>(path: string, params?: Record<string, string>) {
    return this.request<T>(path, { method: 'GET', params })
  }

  post<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: 'DELETE' })
  }

  patch<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    })
  }
}

// Must import store inline to avoid circular dependency
import { useAuthStore } from '@/stores/auth-store'

export const apiClient = new ApiClient()
