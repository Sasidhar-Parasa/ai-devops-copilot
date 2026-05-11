/**
 * useChat — handles conversation state + triggers deploy streaming when
 * a deploy_with_repo intent is detected.
 */
import { useState, useCallback, useRef } from 'react'
import { api } from '../utils/api'
import { useDeployStream } from './useDeployStream'

const SESSION_ID = `s-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`

export function useChat() {
  const [messages,     setMessages]     = useState([{
    id:        'welcome',
    role:      'assistant',
    content:   "Hi! I'm your DevOps Copilot. I can deploy applications, investigate incidents, and monitor your infrastructure.\n\nWhat would you like to do?",
    intent:    'general',
    agents:    [],
    data:      null,
    timestamp: new Date(),
  }])
  const [loading,      setLoading]      = useState(false)
  const [pendingDeploy, setPendingDeploy] = useState(null)
  const historyRef = useRef([])

  // Deploy streaming state
  const deployStream = useDeployStream()

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || loading) return

    const userMsg = {
      id:        `u-${Date.now()}`,
      role:      'user',
      content:   text,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await api.chat(text, SESSION_ID, historyRef.current)

      const assistantMsg = {
        id:          `a-${Date.now()}`,
        role:        'assistant',
        content:     res.response,
        intent:      res.intent,
        agents:      res.agents_used || [],
        data:        res.data,
        timestamp:   new Date(),
        // Mark if this message should show the deploy stream panel
        deployStream: res.intent === 'deploy' && res.data?.deployment?.repo_url
          ? { repoUrl: res.data.deployment.repo_url, appName: res.data.deployment.app_name }
          : null,
      }
      setMessages(prev => [...prev, assistantMsg])

      // Detect pending deploy (asking for repo URL)
      if (res.data?.waiting_for === 'repo_url') {
        setPendingDeploy({ app_name: res.data?.app_name || 'app' })
      } else {
        setPendingDeploy(null)
      }

      // If the backend returned a deploy_with_repo intent, start streaming
      if (res.intent === 'deploy' && res.data?.deployment?.repo_url) {
        const { repo_url, app_name } = res.data.deployment
        deployStream.start(repo_url, app_name || 'app')
      }

      historyRef.current = [
        ...historyRef.current,
        { role: 'user',      content: text },
        { role: 'assistant', content: res.response },
      ].slice(-16)

    } catch (err) {
      setMessages(prev => [...prev, {
        id:        `err-${Date.now()}`,
        role:      'assistant',
        content:   `**Connection error:** ${err.message}\n\nMake sure the backend is running on port 8000.`,
        intent:    'general',
        agents:    [],
        data:      null,
        timestamp: new Date(),
      }])
    } finally {
      setLoading(false)
    }
  }, [loading, deployStream])

  return {
    messages,
    loading,
    sendMessage,
    pendingDeploy,
    sessionId:    SESSION_ID,
    deployStream,
  }
}
