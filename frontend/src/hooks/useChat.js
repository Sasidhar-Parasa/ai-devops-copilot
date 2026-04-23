import { useState, useCallback, useRef } from 'react'
import { api } from '../utils/api'

// Stable session ID for this browser tab
const SESSION_ID = `session-${Date.now()}-${Math.random().toString(36).slice(2,8)}`

export function useChat() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: (
        '## 🤖 AI DevOps Copilot — Ready\n\n' +
        'I\'m your conversational DevOps assistant. I can **actually deploy your apps** to Google Cloud Run!\n\n' +
        '**Try these commands:**\n\n' +
        '- 🚀 `deploy myapp` → I\'ll ask for your GitHub repo\n' +
        '- 🚀 `deploy https://github.com/you/myapp` → Full pipeline: clone → validate → build → deploy\n' +
        '- ⏪ `rollback payment-service`\n' +
        '- 🔍 `why did the deployment fail?`\n' +
        '- 🚨 `any active incidents?`\n' +
        '- 🔧 `auto fix the payment service`\n' +
        '- 📊 `system health check`\n\n' +
        '**Note:** Add `GROQ_API_KEY` or `GEMINI_API_KEY` to `.env` for best conversational quality.'
      ),
      intent: 'general',
      agents: [],
      data: null,
      timestamp: new Date(),
    }
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

      // Track pending deploy state
      if (res.data?.waiting_for === 'repo_url') {
        setPendingDeploy({ app_name: res.data?.app_name })
      } else if (res.data?.deployment || res.data?.rollback) {
        setPendingDeploy(null)
      }

      historyRef.current = [
        ...historyRef.current,
        { role: 'user', content: text },
        { role: 'assistant', content: res.response },
      ].slice(-12)

    } catch (err) {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: (
          '## ⚠️ Connection Error\n\n' +
          `Could not reach the backend.\n\n**Error:** \`${err.message}\`\n\n` +
          'Make sure the backend is running:\n```bash\nuvicorn main:app --port 8000 --reload\n```'
        ),
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
