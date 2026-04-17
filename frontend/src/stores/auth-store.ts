import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface AuthState {
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  user: {
    user_id: string
    username: string
    role: string
    display_name: string
  } | null
  login: (username: string, password: string) => Promise<void>
  setTokens: (accessToken: string, refreshToken: string) => void
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      user: null,

      login: async (username: string, password: string) => {
        const response = await fetch('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        })

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: 'Login failed' }))
          throw new Error(error.detail || 'Login failed')
        }

        const data = await response.json()
        set({
          token: data.access_token,
          refreshToken: data.refresh_token,
          isAuthenticated: true,
        })

        await get().checkAuth()
      },

      setTokens: (accessToken: string, refreshToken: string) => {
        set({ token: accessToken, refreshToken })
      },

      logout: async () => {
        const token = get().token
        if (token) {
          try {
            await fetch('/auth/logout', {
              method: 'POST',
              headers: { Authorization: `Bearer ${token}` },
            })
          } catch {
            // Network failure: still clear local state
          }
        }
        set({
          token: null,
          refreshToken: null,
          isAuthenticated: false,
          user: null,
        })
      },

      checkAuth: async () => {
        let token = get().token
        if (!token) {
          set({ isAuthenticated: false, user: null })
          return
        }

        try {
          let response = await fetch('/auth/me', {
            headers: { Authorization: `Bearer ${token}` },
          })

          // If access token expired, try refresh before giving up
          if (response.status === 401 && get().refreshToken) {
            const refreshResponse = await fetch('/auth/refresh', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ refresh_token: get().refreshToken }),
            })
            if (refreshResponse.ok) {
              const data = await refreshResponse.json()
              set({ token: data.access_token, refreshToken: data.refresh_token })
              token = data.access_token
              response = await fetch('/auth/me', {
                headers: { Authorization: `Bearer ${token}` },
              })
            }
          }

          if (!response.ok) {
            set({ isAuthenticated: false, user: null, token: null })
            return
          }
          const user = await response.json()
          set({ user, isAuthenticated: true })
        } catch {
          set({ isAuthenticated: false, user: null })
        }
      },
    }),
    {
      name: 'hqmts-auth',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
      }),
    },
  ),
)
