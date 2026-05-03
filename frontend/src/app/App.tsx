import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from '@/app/app-shell'
import { ProtectedRoute } from '@/features/auth/protected-route'
import { Skeleton } from '@/shared/ui/skeleton'

const AuthPage = lazy(() => import('@/pages/auth-page').then((module) => ({ default: module.AuthPage })))
const BatchAnalysisPage = lazy(() => import('@/pages/batch-analysis-page').then((module) => ({ default: module.BatchAnalysisPage })))
const NotFoundPage = lazy(() => import('@/pages/not-found-page').then((module) => ({ default: module.NotFoundPage })))
const SingleAnalysisPage = lazy(() => import('@/pages/single-analysis-page').then((module) => ({ default: module.SingleAnalysisPage })))
const TextDetailsPage = lazy(() => import('@/pages/text-details-page').then((module) => ({ default: module.TextDetailsPage })))
const VotePage = lazy(() => import('@/pages/vote-page').then((module) => ({ default: module.VotePage })))

export function App() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <Skeleton className="h-12 w-64" />
          <Skeleton className="h-[320px] w-full rounded-[2rem]" />
          <Skeleton className="h-[240px] w-full rounded-[2rem]" />
        </div>
      }
    >
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<SingleAnalysisPage />} />
          <Route
            path="/batch"
            element={
              <ProtectedRoute>
                <BatchAnalysisPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/vote"
            element={
              <ProtectedRoute>
                <VotePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/texts/:textId"
            element={
              <ProtectedRoute>
                <TextDetailsPage />
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<AuthPage />} />
          <Route path="/register" element={<AuthPage />} />
          <Route path="/auth" element={<LegacyAuthRedirect />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

function LegacyAuthRedirect() {
  const location = useLocation()
  const searchParams = new URLSearchParams(location.search)
  const targetPath = searchParams.get('mode') === 'register' ? '/register' : '/login'
  const redirect = searchParams.get('redirect')
  const nextSearch = new URLSearchParams()

  if (redirect) {
    nextSearch.set('redirect', redirect)
  }

  const search = nextSearch.toString()

  return <Navigate to={search ? `${targetPath}?${search}` : targetPath} replace />
}
