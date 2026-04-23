const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)
  return res.json()
}

export const api = {
  chat: (message, session_id, history = []) =>
    req('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id, history }),
    }),

  session: (session_id) => req(`/session/${session_id}`),

  deployments: (limit = 20) => req(`/deployments?limit=${limit}`),
  deploy: (app_name, version = 'latest', repo_url = '') =>
    req('/deploy', {
      method: 'POST',
      body: JSON.stringify({ app_name, version, config: { repo_url } }),
    }),
  deploySimulate: (app_name, version = 'latest') =>
    req('/deploy/simulate', {
      method: 'POST',
      body: JSON.stringify({ app_name, version }),
    }),
  rollback: (app_name, reason = 'Manual rollback') =>
    req('/rollback', { method: 'POST', body: JSON.stringify({ app_name, reason }) }),

  cloudRunServices: () => req('/cloud-run/services'),

  logs: (limit = 50, level, service) => {
    const params = new URLSearchParams({ limit })
    if (level) params.set('level', level)
    if (service) params.set('service', service)
    return req(`/logs?${params}`)
  },

  health: () => req('/health'),
  incidents: (status) => req(`/incidents${status ? `?status=${status}` : ''}`),
  ping: () => req('/ping'),
}
