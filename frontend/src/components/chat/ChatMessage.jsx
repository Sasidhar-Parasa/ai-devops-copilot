import { useState } from 'react'
import { Bot, User, ChevronDown, ChevronRight, CheckCircle, XCircle, AlertTriangle, ExternalLink, GitBranch, Clock, Loader } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const AGENT_COLORS = {
  coordinator: { bg: 'rgba(179,136,255,0.12)', border: 'rgba(179,136,255,0.3)', color: '#b388ff' },
  deployment:  { bg: 'rgba(0,229,255,0.1)',    border: 'rgba(0,229,255,0.28)',  color: '#00e5ff' },
  monitoring:  { bg: 'rgba(0,255,157,0.1)',    border: 'rgba(0,255,157,0.28)', color: '#00ff9d' },
  incident:    { bg: 'rgba(255,61,87,0.1)',    border: 'rgba(255,61,87,0.28)', color: '#ff3d57' },
  root_cause:  { bg: 'rgba(255,179,0,0.1)',    border: 'rgba(255,179,0,0.28)', color: '#ffb300' },
  fix:         { bg: 'rgba(0,255,157,0.12)',   border: 'rgba(0,255,157,0.3)',  color: '#00ff9d' },
}

const STATUS_ICON = {
  success: <CheckCircle size={11} style={{ color: '#00ff9d' }} />,
  error:   <XCircle    size={11} style={{ color: '#ff3d57' }} />,
  warning: <AlertTriangle size={11} style={{ color: '#ffb300' }} />,
}

const STAGE_STATUS_STYLE = {
  success:   { color: '#00ff9d', symbol: '✓' },
  failed:    { color: '#ff3d57', symbol: '✗' },
  pending:   { color: '#4a5568', symbol: '·' },
}

function PipelinePanel({ deployment }) {
  const [open, setOpen] = useState(true)
  if (!deployment?.stages?.length) return null
  const { status, stages, service_url, app_name, repo_url, error } = deployment

  return (
    <div className="mt-3 rounded-xl overflow-hidden text-xs"
      style={{ border: '1px solid rgba(0,229,255,0.18)', background: 'rgba(0,0,0,0.25)' }}>
      {/* Header */}
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/5 transition-colors"
        style={{ borderBottom: open ? '1px solid rgba(255,255,255,0.05)' : 'none' }}>
        <div className="flex items-center gap-2">
          <GitBranch size={11} style={{ color: 'var(--cyan)' }} />
          <span className="font-mono font-semibold neon-cyan">Deployment Pipeline</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded-full font-medium"
            style={{
              background: status === 'success' ? 'rgba(0,255,157,0.12)' : 'rgba(255,61,87,0.12)',
              color: status === 'success' ? '#00ff9d' : '#ff3d57',
            }}>
            {status}
          </span>
          {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </div>
      </button>

      {open && (
        <div className="p-3 space-y-2 animate-fade-in">
          {/* Stages row */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1">
            {stages.map((stage, i) => {
              const s = STAGE_STATUS_STYLE[stage.status] || STAGE_STATUS_STYLE.pending
              return (
                <div key={i} className="flex items-center flex-shrink-0">
                  <div className="flex flex-col items-center gap-0.5">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center font-bold"
                      style={{ background: `${s.color}18`, border: `1px solid ${s.color}40`, color: s.color }}>
                      {s.symbol}
                    </div>
                    <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>{stage.name}</span>
                    {stage.duration_seconds != null && (
                      <span style={{ color: '#4a5568', fontSize: 9 }}>{stage.duration_seconds}s</span>
                    )}
                  </div>
                  {i < stages.length - 1 && (
                    <div className="w-5 h-px mx-1 flex-shrink-0"
                      style={{ background: `${s.color}40` }} />
                  )}
                </div>
              )
            })}
          </div>

          {/* Live URL */}
          {service_url && (
            <a href={service_url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg font-mono neon-green hover:opacity-80 transition-opacity"
              style={{ background: 'rgba(0,255,157,0.06)', border: '1px solid rgba(0,255,157,0.2)' }}>
              <ExternalLink size={11} />
              {service_url}
            </a>
          )}

          {/* Error */}
          {error && (
            <div className="px-2 py-1.5 rounded-lg font-mono"
              style={{ background: 'rgba(255,61,87,0.08)', border: '1px solid rgba(255,61,87,0.25)', color: '#ff3d57' }}>
              {error}
            </div>
          )}

          {/* Repo */}
          {repo_url && (
            <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>
              Source: <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>{repo_url}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AgentTrace({ agents }) {
  const [open, setOpen] = useState(false)
  if (!agents?.length) return null
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-xs transition-colors"
        style={{ color: 'var(--text-muted)' }}>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        <span>{agents.length} agent{agents.length > 1 ? 's' : ''} used</span>
      </button>
      {open && (
        <div className="mt-2 space-y-1 animate-fade-in">
          {agents.map((step, i) => {
            const c = AGENT_COLORS[step.agent] || AGENT_COLORS.coordinator
            return (
              <div key={i} className="flex items-start gap-2 px-2 py-1.5 rounded-lg text-xs"
                style={{ background: c.bg, border: `1px solid ${c.border}` }}>
                <div className="mt-0.5 flex-shrink-0">{STATUS_ICON[step.status] || STATUS_ICON.success}</div>
                <div className="flex-1 min-w-0">
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded mr-1.5"
                    style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.color }}>
                    {step.agent}
                  </span>
                  <span style={{ color: 'var(--text-secondary)' }}>{step.action}</span>
                  <span className="ml-auto float-right font-mono" style={{ color: '#4a5568', fontSize: 10 }}>
                    {step.duration_ms}ms
                  </span>
                  <div className="mt-0.5 md-content" style={{ color: 'var(--text-secondary)', clear: 'both' }}>
                    <ReactMarkdown>{step.result}</ReactMarkdown>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function ChatMessage({ msg }) {
  const isUser = msg.role === 'user'
  const time = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const deployment = msg.data?.deployment || msg.data?.rollback

  return (
    <div className={`flex gap-3 animate-slide-up ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center"
        style={isUser
          ? { background: 'rgba(179,136,255,0.2)', border: '1px solid rgba(179,136,255,0.3)' }
          : { background: 'rgba(0,229,255,0.12)', border: '1px solid rgba(0,229,255,0.28)' }}>
        {isUser
          ? <User size={14} style={{ color: '#b388ff' }} />
          : <Bot  size={14} className="neon-cyan" />}
      </div>

      <div className={`max-w-[80%] flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
        <div className="rounded-2xl px-4 py-3"
          style={isUser
            ? { background: 'rgba(179,136,255,0.14)', border: '1px solid rgba(179,136,255,0.22)', borderBottomRightRadius: 4 }
            : { background: 'rgba(20,27,45,0.88)', border: '1px solid var(--border)', borderBottomLeftRadius: 4 }}>

          <div className="md-content">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>

          {!isUser && deployment && <PipelinePanel deployment={deployment} />}
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
      <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center"
        style={{ background: 'rgba(0,229,255,0.12)', border: '1px solid rgba(0,229,255,0.28)' }}>
        <Bot size={14} className="neon-cyan" />
      </div>
      <div className="rounded-2xl px-4 py-3 flex items-center gap-1.5"
        style={{ background: 'rgba(20,27,45,0.88)', border: '1px solid var(--border)', borderBottomLeftRadius: 4 }}>
        <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
      </div>
    </div>
  )
}

export function PendingDeployBanner({ app }) {
  if (!app) return null
  return (
    <div className="mx-4 mb-2 px-3 py-2 rounded-lg flex items-center gap-2 text-xs animate-fade-in"
      style={{ background: 'rgba(0,229,255,0.07)', border: '1px solid rgba(0,229,255,0.22)' }}>
      <Clock size={11} className="neon-cyan" />
      <span style={{ color: 'var(--text-secondary)' }}>
        Waiting for GitHub URL to deploy <strong style={{ color: 'var(--cyan)' }}>{app}</strong>
      </span>
    </div>
  )
}
