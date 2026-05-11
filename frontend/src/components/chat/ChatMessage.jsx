import { useState } from 'react'
import { Bot, User, ChevronDown, ChevronRight, CheckCircle, XCircle, AlertTriangle, ExternalLink, GitBranch } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { DeploymentStream } from './DeploymentStream'

const AGENT_COLORS = {
  coordinator: { bg: 'rgba(179,136,255,0.12)', border: 'rgba(179,136,255,0.3)',  color: '#b388ff' },
  deployment:  { bg: 'rgba(0,229,255,0.10)',   border: 'rgba(0,229,255,0.28)',   color: '#00e5ff' },
  monitoring:  { bg: 'rgba(0,255,157,0.10)',   border: 'rgba(0,255,157,0.28)',   color: '#00ff9d' },
  incident:    { bg: 'rgba(255,61,87,0.10)',   border: 'rgba(255,61,87,0.28)',   color: '#ff3d57' },
  root_cause:  { bg: 'rgba(255,179,0,0.10)',   border: 'rgba(255,179,0,0.28)',   color: '#ffb300' },
  fix:         { bg: 'rgba(0,255,157,0.12)',   border: 'rgba(0,255,157,0.30)',   color: '#00ff9d' },
}

const STATUS_ICON = {
  success: <CheckCircle  size={11} style={{ color: '#00ff9d' }} />,
  error:   <XCircle      size={11} style={{ color: '#ff3d57' }} />,
  warning: <AlertTriangle size={11} style={{ color: '#ffb300' }} />,
}

function AgentTrace({ agents }) {
  const [open, setOpen] = useState(false)
  if (!agents?.length) return null
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-xs transition-colors"
        style={{ color: 'var(--text-muted)' }}
      >
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        <span>{agents.length} agent{agents.length > 1 ? 's' : ''} used</span>
      </button>
      {open && (
        <div className="mt-2 space-y-1 animate-fade-in">
          {agents.map((step, i) => {
            const c = AGENT_COLORS[step.agent] || AGENT_COLORS.coordinator
            return (
              <div
                key={i}
                className="flex items-start gap-2 px-2 py-1.5 rounded-lg text-xs"
                style={{ background: c.bg, border: `1px solid ${c.border}` }}
              >
                <div className="mt-0.5 flex-shrink-0">
                  {STATUS_ICON[step.status] || STATUS_ICON.success}
                </div>
                <div className="flex-1 min-w-0">
                  <span
                    className="font-mono text-[10px] px-1.5 py-0.5 rounded mr-1.5"
                    style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.color }}
                  >
                    {step.agent}
                  </span>
                  <span style={{ color: 'var(--text-secondary)' }}>{step.action}</span>
                  <span className="ml-auto float-right font-mono" style={{ color: '#4a5568', fontSize: 10 }}>
                    {step.duration_ms}ms
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function ChatMessage({ msg, deployStream }) {
  const isUser = msg.role === 'user'
  const time   = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  // Should this message show the live deploy stream?
  const showStream = (
    !isUser &&
    deployStream &&
    msg.intent === 'deploy' &&
    (deployStream.running || deployStream.events.length > 0 || deployStream.result)
  )

  return (
    <div className={`flex gap-3 animate-slide-up ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center"
        style={isUser
          ? { background: 'rgba(179,136,255,0.2)', border: '1px solid rgba(179,136,255,0.3)' }
          : { background: 'rgba(0,229,255,0.12)',  border: '1px solid rgba(0,229,255,0.28)' }}
      >
        {isUser
          ? <User size={14} style={{ color: '#b388ff' }} />
          : <Bot  size={14} className="neon-cyan" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[82%] flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className="rounded-2xl px-4 py-3"
          style={isUser
            ? { background: 'rgba(179,136,255,0.14)', border: '1px solid rgba(179,136,255,0.22)', borderBottomRightRadius: 4 }
            : { background: 'rgba(20,27,45,0.88)',    border: '1px solid var(--border)',          borderBottomLeftRadius: 4 }}
        >
          <div className="md-content">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>

          {/* Live deployment stream */}
          {showStream && (
            <DeploymentStream
              events={deployStream.events}
              active={deployStream.active}
              result={deployStream.result}
              running={deployStream.running}
              repoUrl={msg.deployStream?.repoUrl}
            />
          )}

          {!isUser && <AgentTrace agents={msg.agents} />}
        </div>
        <span className="text-xs px-1" style={{ color: 'var(--text-muted)' }}>{time}</span>
      </div>
    </div>
  )
}

export function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade-in">
      <div
        className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center"
        style={{ background: 'rgba(0,229,255,0.12)', border: '1px solid rgba(0,229,255,0.28)' }}
      >
        <Bot size={14} className="neon-cyan" />
      </div>
      <div
        className="rounded-2xl px-4 py-3 flex items-center gap-1.5"
        style={{ background: 'rgba(20,27,45,0.88)', border: '1px solid var(--border)', borderBottomLeftRadius: 4 }}
      >
        <div className="typing-dot" />
        <div className="typing-dot" />
        <div className="typing-dot" />
      </div>
    </div>
  )
}

export function PendingDeployBanner({ app }) {
  if (!app) return null
  return (
    <div
      className="mx-4 mb-2 px-3 py-2 rounded-lg flex items-center gap-2 text-xs animate-fade-in"
      style={{ background: 'rgba(0,229,255,0.07)', border: '1px solid rgba(0,229,255,0.22)' }}
    >
      <GitBranch size={11} style={{ color: 'var(--cyan)' }} />
      <span style={{ color: 'var(--text-secondary)' }}>
        Paste GitHub URL to deploy <strong style={{ color: 'var(--cyan)' }}>{app}</strong>
      </span>
    </div>
  )
}
