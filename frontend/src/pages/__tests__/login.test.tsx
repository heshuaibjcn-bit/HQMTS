import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LoginPage } from '../login'
import { renderWithProviders } from '@/test/utils'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

// Mock auth store login
vi.mock('@/stores/auth-store', async () => {
  const { useAuthStore } = await vi.importActual<typeof import('@/stores/auth-store')>('@/stores/auth-store')
  return { useAuthStore }
})

describe('LoginPage', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
  })

  it('renders login form with title', () => {
    renderWithProviders(<LoginPage />)
    expect(screen.getByText('HQMTS 登录')).toBeInTheDocument()
  })

  it('renders username and password fields', () => {
    renderWithProviders(<LoginPage />)
    expect(screen.getByLabelText('用户名')).toBeInTheDocument()
    expect(screen.getByLabelText('密码')).toBeInTheDocument()
  })

  it('renders submit button', () => {
    renderWithProviders(<LoginPage />)
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument()
  })

  it('shows validation errors for empty fields', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoginPage />)
    const submitBtn = screen.getByRole('button', { name: '登录' })
    await user.click(submitBtn)
    // HTML5 validation prevents form submission for required fields
    const usernameInput = screen.getByLabelText('用户名') as HTMLInputElement
    expect(usernameInput.validity.valid).toBe(false)
  })

  it('shows loading state during submission', async () => {
    const user = userEvent.setup()

    const { useAuthStore } = await import('@/stores/auth-store')
    const originalLogin = useAuthStore.getState().login
    // Make login hang indefinitely
    let resolveLogin: () => void
    useAuthStore.setState({
      login: () => new Promise<void>((r) => { resolveLogin = r }),
    })

    renderWithProviders(<LoginPage />)

    await user.type(screen.getByLabelText('用户名'), 'testuser')
    await user.type(screen.getByLabelText('密码'), 'testpass')
    await user.click(screen.getByRole('button'))

    // Should show loading text
    await waitFor(() => {
      expect(screen.getByRole('button')).toHaveTextContent('登录中...')
    })

    // Resolve to clean up
    resolveLogin!()
    useAuthStore.setState({ login: originalLogin })
  })

  it('navigates on successful login', async () => {
    const user = userEvent.setup()

    // Mock successful login
    const { useAuthStore } = await import('@/stores/auth-store')
    const originalLogin = useAuthStore.getState().login
    useAuthStore.setState({
      login: async () => {
        // Simulate success
      },
    })

    renderWithProviders(<LoginPage />)

    await user.type(screen.getByLabelText('用户名'), 'testuser')
    await user.type(screen.getByLabelText('密码'), 'testpass')
    await user.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/')
    })

    // Restore
    useAuthStore.setState({ login: originalLogin })
  })

  it('shows error message on login failure', async () => {
    const user = userEvent.setup()

    const { useAuthStore } = await import('@/stores/auth-store')
    const originalLogin = useAuthStore.getState().login
    useAuthStore.setState({
      login: async () => {
        throw new Error('Invalid credentials')
      },
    })

    renderWithProviders(<LoginPage />)

    await user.type(screen.getByLabelText('用户名'), 'baduser')
    await user.type(screen.getByLabelText('密码'), 'badpass')
    await user.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
    })

    useAuthStore.setState({ login: originalLogin })
  })
})
