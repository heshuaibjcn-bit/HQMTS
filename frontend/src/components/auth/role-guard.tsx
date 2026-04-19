import { useAuthStore } from '@/stores/auth-store'

interface Props {
  allowedRoles: string[]
  children: React.ReactNode
  fallback?: React.ReactNode
}

export function RoleGuard({ allowedRoles, children, fallback }: Props) {
  const user = useAuthStore((s) => s.user)
  if (!user || !allowedRoles.includes(user.role)) {
    return fallback ? <>{fallback}</> : null
  }
  return <>{children}</>
}
