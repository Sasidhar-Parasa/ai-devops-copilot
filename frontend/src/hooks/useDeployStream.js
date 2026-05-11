/**
 * useDeployStream — subscribes to SSE /api/deploy/stream.
 * Returns live events so the UI updates in real time.
 */
import { useState, useCallback, useRef } from 'react'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export const STAGE_LABELS = {
  preflight: 'Pre-flight checks',
  clone:     'Cloning repository',
  analyze:   'Analyzing repo',
  build:     'Building & pushing image',
  deploy:    'Deploying to Cloud Run',
  health:    'Health check',
}

export function useDeployStream() {
  const [events,  setEvents]  = useState([])
  const [active,  setActive]  = useState(null)
  const [result,  setResult]  = useState(null)
  const [running, setRunning] = useState(false)
  const esRef = useRef(null)

  const reset = useCallback(() => {
    setEvents([])
    setActive(null)
    setResult(null)
    setRunning(false)
  }, [])

  const start = useCallback((repoUrl, appName, version = 'latest') => {
    if (esRef.current) esRef.current.close()
    reset()
    setRunning(true)

    const params = new URLSearchParams({ repo_url: repoUrl, app_name: appName, version })
    const es = new EventSource(`${BASE}/deploy/stream?${params}`)
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data)
        if (evt.stage === 'done') {
          setResult(evt)
          setRunning(false)
          setActive(null)
          es.close()
          return
        }
        setActive(evt.stage)
        setEvents(prev => {
          // Replace running entry when final status arrives for same stage
          const idx = prev.findIndex(p => p.stage === evt.stage && p.status === 'running')
          if (idx !== -1 && evt.status !== 'running') {
            const next = [...prev]
            next[idx] = evt
            return next
          }
          // Avoid exact duplicates
          const dup = prev.findIndex(p => p.stage === evt.stage && p.status === evt.status && p.message === evt.message)
          if (dup !== -1) return prev
          return [...prev, evt]
        })
      } catch (_) { /* ignore */ }
    }

    es.onerror = () => {
      setRunning(false)
      setResult({ status: 'failed', error: 'Lost connection to deployment server.' })
      es.close()
    }
  }, [reset])

  const stop = useCallback(() => {
    esRef.current?.close()
    setRunning(false)
  }, [])

  return { events, active, result, running, start, stop, reset }
}
