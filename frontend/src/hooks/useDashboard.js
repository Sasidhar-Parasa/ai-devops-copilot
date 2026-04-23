import { useState, useEffect, useCallback } from 'react'
import { api } from '../utils/api'

export function useDashboard() {
  const [health, setHealth] = useState(null)
  const [deployments, setDeployments] = useState([])
  const [logs, setLogs] = useState([])
  const [incidents, setIncidents] = useState([])
  const [cloudRunServices, setCloudRunServices] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [h, d, l, i] = await Promise.all([
        api.health(),
        api.deployments(10),
        api.logs(30),
        api.incidents(),
      ])
      setHealth(h)
      setDeployments(d.deployments || [])
      setLogs(l.logs || [])
      setIncidents(i.incidents || [])

      // Try to fetch real Cloud Run services (non-blocking)
      api.cloudRunServices()
        .then(r => setCloudRunServices(r.services || []))
        .catch(() => {})

      setLastRefresh(new Date())
    } catch (err) {
      console.error('Dashboard refresh failed:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 20000)
    return () => clearInterval(interval)
  }, [refresh])

  return { health, deployments, logs, incidents, cloudRunServices, loading, lastRefresh, refresh }
}
