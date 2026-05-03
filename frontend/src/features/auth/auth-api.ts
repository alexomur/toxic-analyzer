import { apiRequest, ApiError } from '@/shared/api/client'
import type { AuthActorResponse, AuthSessionResponse, LoginPayload, RegisterPayload } from '@/features/auth/auth-types'

export const sessionQueryKey = ['auth', 'session'] as const

export async function getCurrentActor() {
  try {
    return await apiRequest<AuthActorResponse>('/api/v1/auth/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null
    }

    throw error
  }
}

export function login(payload: LoginPayload) {
  return apiRequest<AuthSessionResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: payload,
  })
}

export function register(payload: RegisterPayload) {
  return apiRequest<AuthSessionResponse>('/api/v1/auth/register', {
    method: 'POST',
    body: payload,
  })
}

export function logout() {
  return apiRequest<void>('/api/v1/auth/logout', {
    method: 'POST',
  })
}
