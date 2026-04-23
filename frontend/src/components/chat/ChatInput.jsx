import { useState, useRef, useEffect } from 'react'
import { Send, Zap, GitBranch } from 'lucide-react'

const QUICK_COMMANDS = [
  { label: '🚀 Deploy', cmd: 'deploy myapp' },
  { label: '📋 Logs',   cmd: 'show me recent errors' },
  { label: '🔍 RCA',    cmd: 'why did the last deployment fail?' },
  { label: '🚨 Alerts', cmd: 'show active incidents' },
  { label: '🔧 Auto-fix', cmd: 'auto fix the payment service' },
  { label: '📊 Health', cmd: 'system health check' },
]

export function ChatInput({ onSend, loading, pendingDeploy }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)

  // If we're waiting for a repo URL, pre-fill hint
  const placeholder = pendingDeploy
    ? `Paste your GitHub URL here: https://github.com/user/${pendingDeploy.app_name}`
    : 'Ask anything... "deploy https://github.com/you/myapp" or "why did the deploy fail?"'

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px'
    }
  }, [value])

  const submit = () => {
    if (value.trim() && !loading) {
      onSend(value.trim())
      setValue('')
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  return (
    <div className="border-t p-4" style={{ borderColor: 'var(--border)', background: 'rgba(11,15,26,0.95)' }}>
      {/* Quick commands */}
      <div className="flex gap-2 mb-3 flex-wrap">
        {QUICK_COMMANDS.map(({ label, cmd }) => (
          <button key={cmd} onClick={() => onSend(cmd)} disabled={loading}
            className="text-xs px-3 py-1.5 rounded-full transition-all duration-200 hover:scale-105 disabled:opacity-40"
            style={{ background: 'rgba(0,229,255,0.08)', border: '1px solid rgba(0,229,255,0.18)', color: 'var(--cyan)' }}>
            {label}
          </button>
        ))}
      </div>

      {/* Pending deploy hint */}
      {pendingDeploy && (
        <div className="mb-2 flex items-center gap-2 text-xs px-2 py-1.5 rounded-lg"
          style={{ background: 'rgba(0,229,255,0.06)', border: '1px solid rgba(0,229,255,0.15)' }}>
          <GitBranch size={11} style={{ color: 'var(--cyan)' }} />
          <span style={{ color: 'var(--text-secondary)' }}>
            Paste GitHub repo URL below to deploy <strong style={{ color: 'var(--cyan)' }}>{pendingDeploy.app_name}</strong>
          </span>
        </div>
      )}

      {/* Input row */}
      <div className="flex gap-3 items-end rounded-xl p-3"
        style={{ background: 'rgba(20,27,45,0.8)', border: `1px solid ${pendingDeploy ? 'rgba(0,229,255,0.4)' : 'rgba(0,229,255,0.2)'}` }}>
        <Zap size={16} className="flex-shrink-0 mb-1.5 neon-cyan" />
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          rows={1}
          disabled={loading}
          className="flex-1 bg-transparent resize-none outline-none text-sm placeholder:opacity-40"
          style={{ color: 'var(--text-primary)', lineHeight: '1.5', minHeight: '24px', fontFamily: 'Inter, sans-serif' }}
        />
        <button onClick={submit} disabled={!value.trim() || loading}
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200 hover:scale-110 disabled:opacity-30 disabled:scale-100"
          style={{ background: 'linear-gradient(135deg, rgba(0,229,255,0.3), rgba(179,136,255,0.3))', border: '1px solid rgba(0,229,255,0.4)' }}>
          <Send size={14} className="neon-cyan" />
        </button>
      </div>
      <p className="text-center text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
        <kbd className="font-mono px-1 rounded" style={{ background: 'rgba(255,255,255,0.06)' }}>Enter</kbd> to send ·
        <kbd className="font-mono px-1 rounded ml-1" style={{ background: 'rgba(255,255,255,0.06)' }}>Shift+Enter</kbd> new line
      </p>
    </div>
  )
}
