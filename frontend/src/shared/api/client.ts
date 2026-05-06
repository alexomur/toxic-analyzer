import { env } from '@/shared/config/env'
import { getCsrfToken } from '@/shared/api/csrf'
import { resolveProblemMessage } from '@/shared/api/error-resolver'
import type { ProblemDetails } from '@/shared/api/types'

export class ApiError extends Error {
  public readonly status: number
  public readonly problem: ProblemDetails | null

  constructor(message: string, status: number, problem: ProblemDetails | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
}

function buildUrl(path: string) {
  if (/^https?:\/\//.test(path)) {
    return path
  }

  return `${env.apiBaseUrl}${path}`
}

async function parseBody(response: Response) {
  const contentType = response.headers.get('content-type') ?? ''

  if (!contentType.includes('application/json')) {
    return null
  }

  return response.json()
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, method = 'GET', ...restOptions } = options
  const nextHeaders = new Headers(headers)
  const isUnsafeMethod = !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method.toUpperCase())

  if (body !== undefined && !(body instanceof FormData)) {
    nextHeaders.set('Content-Type', 'application/json')
  }

  if (isUnsafeMethod) {
    const csrfToken = getCsrfToken()
    if (csrfToken) {
      nextHeaders.set('X-CSRF-Token', csrfToken)
    }
  }

  const response = await fetch(buildUrl(path), {
    ...restOptions,
    method,
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    headers: nextHeaders,
    credentials: 'include',
  })

  const parsedBody = await parseBody(response)

  if (!response.ok) {
    const problem = parsedBody && typeof parsedBody === 'object' ? (parsedBody as ProblemDetails) : null
    throw new ApiError(resolveProblemMessage(problem, response.status, response.statusText, path, method), response.status, problem)
  }

  return parsedBody as T
}
