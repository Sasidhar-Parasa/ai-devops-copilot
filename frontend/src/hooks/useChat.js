import { useState, useCallback, useRef } from 'react'
import { api } from '../utils/api'

const SESSION_ID = `s-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`

export function useChat() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hi! I'm your DevOps Copilot. I can help you deploy applications, investigate incidents, and monitor your infrastructure.\n\nWhat would you like to do?",
      intent: 'general',
      agents: [],
      data: null,
      timestamp: new Date(),
    },
  ])
  const [loading, setLoading] = useState(false)
  const [pendingDeploy, setPendingDeploy] = useState(null)
  const historyRef = useRef([])

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || loading) return

    const userMsg = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await api.chat(text, SESSION_ID, historyRef.current)
      const assistantMsg = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: res.response,
        intent: res.intent,
        agents: res.agents_used || [],
        data: res.data,
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, assistantMsg])

      if (res.data?.waiting_for === 'repo_url') {
        setPendingDeploy({ app_name: res.data?.app_name || 'app' })
      } else if (res.data?.deployment) {
        setPendingDeploy(null)
      }

      historyRef.current = [
        ...historyRef.current,
        { role: 'user', content: text },
        { role: 'assistant', content: res.response },
      ].slice(-16)
    } catch (err) {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `**Connection error:** ${err.message}\n\nMake sure the backend is running on port 8000.`,
        intent: 'general',
        agents: [],
        data: null,
        timestamp: new Date(),
      }])
    } finally {
      setLoading(false)
    }
  }, [loading])

  return { messages, loading, sendMessage, pendingDeploy, sessionId: SESSION_ID }
}
