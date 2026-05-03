import { createContext, useContext, useEffect, useMemo, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCurrentActor, login, logout, register, sessionQueryKey } from '@/features/auth/auth-api'
import type { AuthActorResponse, LoginPayload, RegisterPayload } from '@/features/auth/auth-types'
import { setCsrfToken } from '@/shared/api/csrf'

interface AuthContextValue {
  session: AuthActorResponse | null | undefined
  isAuthenticated: boolean
  isRestoring: boolean
  login: (payload: LoginPayload) => Promise<AuthActorResponse | null>
  register: (payload: RegisterPayload) => Promise<AuthActorResponse | null>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const sessionQuery = useQuery({
    queryKey: sessionQueryKey,
    queryFn: getCurrentActor,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  useEffect(() => {
    setCsrfToken(sessionQuery.data?.csrfToken ?? null)
  }, [sessionQuery.data])

  const authMutation = useMutation({
    mutationFn: async ({
      mode,
      payload,
    }: {
      mode: 'login' | 'register'
      payload: LoginPayload | RegisterPayload
    }) => {
      const sessionResponse = mode === 'login' ? await login(payload as LoginPayload) : await register(payload as RegisterPayload)
      setCsrfToken(sessionResponse.csrfToken)
      return queryClient.fetchQuery({
        queryKey: sessionQueryKey,
        queryFn: getCurrentActor,
      })
    },
  })

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await logout()
    },
    onSettled: async () => {
      setCsrfToken(null)
      await queryClient.cancelQueries({ queryKey: sessionQueryKey })
      queryClient.setQueryData(sessionQueryKey, null)
    },
  })

  const value = useMemo<AuthContextValue>(
    () => ({
      session: sessionQuery.data,
      isAuthenticated: Boolean(sessionQuery.data),
      isRestoring: sessionQuery.isPending,
      login: async (payload) => authMutation.mutateAsync({ mode: 'login', payload }),
      register: async (payload) => authMutation.mutateAsync({ mode: 'register', payload }),
      logout: async () => {
        await logoutMutation.mutateAsync()
      },
    }),
    [authMutation, logoutMutation, sessionQuery.data, sessionQuery.isPending],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider.')
  }

  return context
}
