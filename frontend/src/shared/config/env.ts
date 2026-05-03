const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() ?? ''

export const env = {
  apiBaseUrl: rawApiBaseUrl.endsWith('/') ? rawApiBaseUrl.slice(0, -1) : rawApiBaseUrl,
  isDev: import.meta.env.DEV,
}
