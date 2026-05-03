export interface AuthSessionResponse {
  actorType: string
  email: string
  username: string | null
  csrfToken: string
  expiresAt: string
  capabilities: string[]
}

export interface AuthActorResponse {
  actorType: string
  subjectId: string
  clientId: string | null
  tenantId: string | null
  sessionId: string | null
  authScheme: string
  email: string | null
  name: string | null
  csrfToken: string | null
  roles: string[]
  capabilities: string[]
  scopes: string[]
}

export interface RegisterPayload {
  email: string
  password: string
  username?: string
}

export interface LoginPayload {
  email: string
  password: string
}
