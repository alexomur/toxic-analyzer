import type { ReactElement } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/features/auth/auth-context'
import { Skeleton } from '@/shared/ui/skeleton'

export function ProtectedRoute({ children }: { children: ReactElement }) {
  const { isAuthenticated, isRestoring } = useAuth()
  const location = useLocation()

  if (isRestoring) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-56" />
        <Skeleton className="h-64 w-full rounded-[2rem]" />
      </div>
    )
  }

  if (!isAuthenticated) {
    const redirect = `${location.pathname}${location.search}`
    return <Navigate to={`/login?redirect=${encodeURIComponent(redirect)}`} replace />
  }

  return children
}
