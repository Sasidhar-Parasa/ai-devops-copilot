import { useState, useRef, useEffect } from 'react'
import { Send, Zap, GitBranch } from 'lucide-react'

// Contextual suggestions — change based on whether we're waiting for a repo URL
const DEFAULT_SUGGESTIONS = [
  { label: 'Deploy an app',       cmd: 'I want to deploy my application' },
  { label: 'Check system health', cmd: 'How is the system health?' },
  { label: 'View recent logs',    cmd: 'Show me recent errors' },
  { label: 'Any incidents?',      cmd: 'Are there any active incidents?' },
]

export function ChatInput({ onSend, loading, pendingDeploy }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)
  const waitingForRepo = Boolean(pendingDeploy)

  const placeholder = waitingForRepo
    ? `Paste GitHub URL: https://github.com/you/${pendingDeploy}...`
    : 'Ask me anything — deploy an app, check logs, investigate an incident...'

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 130) + 'px'
    }
  }, [value])

  const submit = () => {
    if (value.trim() && !loading) {
      onSend(value.trim())
      setValue('')
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
    }
  }

  return (
    <div className="border-t" style={{ borderColor: 'var(--border)', background: 'rgba(11,15,26,0.97)' }}>
      {/* Quick suggestions — only show when not waiting for repo */}
      {!waitingForRepo && (
        <div className="px-4 pt-3 flex gap-2 flex-wrap">
          {DEFAULT_SUGGESTIONS.map(({ label, cmd }) => (
            <button key={cmd} onClick={() => onSend(cmd)} disabled={loading}
              className="text-xs px-3 py-1.5 rounded-full transition-all hover:scale-105 disabled:opacity-40"
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.09)', color: 'var(--text-secondary)' }}>
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Repo URL hint */}
      {waitingForRepo && (
        <div className="px-4 pt-3 flex items-center gap-2 text-xs"
          style={{ color: 'var(--text-secondary)' }}>
          <GitBranch size={11} style={{ color: 'var(--cyan)' }} />
          Paste your GitHub repo URL below to deploy <strong style={{ color: 'var(--cyan)' }}>{pendingDeploy}</strong>
        </div>
      )}

      {/* Input */}
      <div className="p-4">
        <div className="flex gap-3 items-end rounded-xl px-4 py-3"
          style={{
            background: 'rgba(20,27,45,0.8)',
            border: `1px solid ${waitingForRepo ? 'rgba(0,229,255,0.4)' : 'rgba(0,229,255,0.18)'}`,
          }}>
          <Zap size={15} className="flex-shrink-0 mb-1 neon-cyan" />
          <textarea
            ref={textareaRef}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
            placeholder={placeholder}
            rows={1}
            disabled={loading}
            className="flex-1 bg-transparent resize-none outline-none text-sm placeholder:opacity-35"
            style={{ color: 'var(--text-primary)', lineHeight: '1.5', minHeight: '22px', fontFamily: 'Inter, sans-serif' }}
          />
          <button onClick={submit} disabled={!value.trim() || loading}
            className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center transition-all hover:scale-110 disabled:opacity-30"
            style={{ background: 'linear-gradient(135deg, rgba(0,229,255,0.25), rgba(179,136,255,0.25))', border: '1px solid rgba(0,229,255,0.35)' }}>
            <Send size={13} className="neon-cyan" />
          </button>
        </div>
        <p className="text-center text-xs mt-1.5" style={{ color: 'var(--text-muted)' }}>
          <kbd className="font-mono px-1 rounded" style={{ background: 'rgba(255,255,255,0.05)' }}>Enter</kbd> send ·
          <kbd className="font-mono px-1 rounded ml-1" style={{ background: 'rgba(255,255,255,0.05)' }}>Shift+Enter</kbd> newline
        </p>
      </div>
    </div>
  )
}
