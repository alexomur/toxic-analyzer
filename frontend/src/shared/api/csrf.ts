let csrfToken: string | null = null

export function setCsrfToken(nextToken: string | null | undefined) {
  csrfToken = nextToken ?? null
}

export function getCsrfToken() {
  return csrfToken
}
