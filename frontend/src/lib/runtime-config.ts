type ApiMetaResponse = {
  base_url?: unknown
  websocket?: {
    url?: unknown
  } | null
}

export type RuntimeConfig = {
  apiBaseUrl: string
  wsUrl: string
}

const META_PATHS = ['/api/v1/meta', '/api/meta']
const META_FETCH_TIMEOUT_MS = 5000

let runtimeConfigPromise: Promise<RuntimeConfig> | null = null

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '')
}

function normalizeHttpUrl(value: string | undefined | null) {
  if (!value) {
    return null
  }
  const trimmed = value.trim()
  return trimmed ? trimTrailingSlash(trimmed) : null
}

function normalizeWsUrl(value: string | undefined | null) {
  if (!value) {
    return null
  }
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function buildSameOriginWsUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/ws`
}

function buildConfig(apiBaseUrl: string | null, wsUrl: string | null): RuntimeConfig {
  const resolvedApiBaseUrl = apiBaseUrl ?? ''
  const resolvedWsUrl = wsUrl
    ?? (resolvedApiBaseUrl ? `${resolvedApiBaseUrl.replace(/^http/i, 'ws')}/api/v1/ws` : buildSameOriginWsUrl())

  return {
    apiBaseUrl: resolvedApiBaseUrl,
    wsUrl: resolvedWsUrl,
  }
}

async function fetchMetaConfig() {
  for (const path of META_PATHS) {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), META_FETCH_TIMEOUT_MS)
    try {
      const response = await fetch(path, {
        credentials: 'omit',
        signal: controller.signal,
      })
      if (!response.ok) {
        continue
      }

      const contentType = response.headers.get('content-type') ?? ''
      if (!contentType.includes('application/json')) {
        continue
      }

      const payload = await response.json() as ApiMetaResponse
      const apiBaseUrl = typeof payload.base_url === 'string' ? normalizeHttpUrl(payload.base_url) : null
      const wsUrl = typeof payload.websocket?.url === 'string' ? normalizeWsUrl(payload.websocket.url) : null
      if (apiBaseUrl || wsUrl) {
        return buildConfig(apiBaseUrl, wsUrl)
      }
    } catch {
      // Ignore metadata fetch failures and fall back to env or same-origin defaults.
    } finally {
      window.clearTimeout(timer)
    }
  }

  return null
}

export async function getRuntimeConfig() {
  if (!runtimeConfigPromise) {
    runtimeConfigPromise = (async () => {
      const explicitApiBaseUrl = normalizeHttpUrl(import.meta.env.VITE_API_BASE_URL as string | undefined)
      const explicitWsUrl = normalizeWsUrl(import.meta.env.VITE_WS_BASE_URL as string | undefined)

      if (explicitApiBaseUrl || explicitWsUrl) {
        return buildConfig(explicitApiBaseUrl, explicitWsUrl)
      }

      const metaConfig = await fetchMetaConfig()
      if (metaConfig) {
        return metaConfig
      }

      return buildConfig(null, null)
    })()
  }

  return runtimeConfigPromise
}
