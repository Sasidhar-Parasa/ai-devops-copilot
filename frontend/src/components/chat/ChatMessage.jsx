import { Bot, User, ChevronDown, ChevronRight, CheckCircle, XCircle, AlertTriangle, ExternalLink, GitBranch, Clock } from 'lucide-react'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

const AGENT_COLORS = {
  coordinator: { bg: 'rgba(179,136,255,0.15)', border: 'rgba(179,136,255,0.35)', color: '#b388ff' },
  deployment:  { bg: 'rgba(0,229,255,0.12)',   border: 'rgba(0,229,255,0.3)',    color: '#00e5ff' },
  monitoring:  { bg: 'rgba(0,255,157,0.12)',   border: 'rgba(0,255,157,0.3)',    color: '#00ff9d' },
  incident:    { bg: 'rgba(255,61,87,0.12)',   border: 'rgba(255,61,87,0.3)',    color: '#ff3d57' },
  root_cause:  { bg: 'rgba(255,179,0,0.12)',   border: 'rgba(255,179,0,0.3)',    color: '#ffb300' },
  fix:         { bg: 'rgba(0,255,157,0.15)',   border: 'rgba(0,255,157,0.35)',   color: '#00ff9d' },
}

const STATUS_ICON = {
  success: <CheckCircle size={12} style={{ color: '#00ff9d' }} />,
  error:   <XCircle size={12} style={{ color: '#ff3d57' }} />,
  warning: <AlertTriangle size={12} style={{ color: '#ffb300' }} />,
}

const STAGE_STATUS_COLORS = {
  success:   '#00ff9d',
  failed:    '#ff3d57',
  pending:   '#4a5568',
  simulated: '#ffb300',
}

function PipelineInline({ stages = [], serviceUrl, status }) {
  if (!stages.length) return null
  return (
    <div className="mt-3 rounded-xl overflow-hidden" style={{ border: '1px solid rgba(0,229,255,0.15)', background: 'rgba(0,0,0,0.2)' }}>
      <div className="px-3 py-2 flex items-center gap-2" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(0,229,255,0.05)' }}>
        <GitBranch size={12} style={{ color: 'var(--cyan)' }} />
        <span className="text-xs font-mono font-semibold neon-cyan">Pipeline</span>
        <span className="text-xs ml-auto" style={{ color: 'var(--text-muted)' }}>
          {stages.filter(s => s.status === 'success').length}/{stages.length} stages
        </span>
      </div>
      <div className="flex items-center gap-1 px-3 py-3">
        {stages.map((stage, i) => {
          const color = STAGE_STATUS_COLORS[stage.status] || '#4a5568'
          const isLast = i === stages.length - 1
          return (
            <div key={i} className="flex items-center">
              <div className="flex flex-col items-center gap-1">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs"
                  style={{ background: color + '18', border: `1px solid ${color}50`, color }}>
                  {stage.status === 'success' ? '✓' : stage.status === 'failed' ? '✗' : stage.status === 'simulated' ? '~' : '·'}
                </div>
                <span style={{ color: 'var(--text-muted)', fontSize: 10, whiteSpace: 'nowrap' }}>{stage.name}</span>
                {stage.duration_seconds && (
                  <span style={{ color: '#4a5568', fontSize: 9 }}>{stage.duration_seconds}s</span>
                )}
              </div>
              {!isLast && (
                <div className="w-6 h-px mx-1" style={{ background: color + '40' }} />
              )}
            </div>
          )
        })}
      </div>
      {serviceUrl && serviceUrl !== 'https://myapp-simulated.run.app' && !serviceUrl.includes('simulated') && (
        <div className="px-3 py-2" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <a href={serviceUrl} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs neon-green hover:opacity-80 transition-opacity">
            <ExternalLink size={11} />
            <span className="font-mono">{serviceUrl}</span>
          </a>
        </div>
      )}
    </div>
  )
}

function AgentTrace({ agents }) {
  const [open, setOpen] = useState(false)
  if (!agents?.length) return null
  return (
    <div className="mt-3">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 text-xs transition-colors"
        style={{ color: 'var(--text-secondary)' }}>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span>Agent execution trace</span>
        <span className="font-mono px-1.5 py-0.5 rounded text-xs"
          style={{ background: 'rgba(0,229,255,0.1)', color: 'var(--cyan)' }}>
          {agents.length} agent{agents.length > 1 ? 's' : ''}
        </span>
      </button>
      {open && (
        <div className="mt-2 space-y-1.5 animate-fade-in">
          {agents.map((step, i) => {
            const c = AGENT_COLORS[step.agent] || AGENT_COLORS.coordinator
            return (
              <div key={i} className="flex items-start gap-2 p-2 rounded-lg"
                style={{ background: c.bg, border: `1px solid ${c.border}` }}>
                <div className="flex-shrink-0 mt-0.5">{STATUS_ICON[step.status] || STATUS_ICON.success}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="agent-badge" style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.color }}>
                      {step.agent}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{step.action}</span>
                    <span className="text-xs font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>{step.duration_ms}ms</span>
                  </div>
                  <div className="text-xs mt-1 md-content" style={{ color: 'var(--text-secondary)' }}>
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
  const deployment = msg.data?.deployment
  const rollback = msg.data?.rollback

  return (
    <div className={`flex gap-3 animate-slide-up ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
        style={isUser
          ? { background: 'rgba(179,136,255,0.2)', border: '1px solid rgba(179,136,255,0.3)' }
          : { background: 'rgba(0,229,255,0.15)', border: '1px solid rgba(0,229,255,0.3)' }}>
        {isUser
          ? <User size={14} style={{ color: '#b388ff' }} />
          : <Bot size={14} className="neon-cyan" />}
      </div>

      <div className={`max-w-[80%] flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
        <div className="rounded-2xl px-4 py-3"
          style={isUser
            ? { background: 'rgba(179,136,255,0.15)', border: '1px solid rgba(179,136,255,0.25)', borderBottomRightRadius: 4 }
            : { background: 'rgba(20,27,45,0.9)', border: '1px solid var(--border)', borderBottomLeftRadius: 4 }}>

          <div className="md-content">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>

          {/* Show pipeline inline for deploy results */}
          {!isUser && deployment?.stages && (
            <PipelineInline
              stages={deployment.stages}
              serviceUrl={deployment.service_url}
              status={deployment.status}
            />
          )}
          {!isUser && rollback?.stages && (
            <PipelineInline stages={rollback.stages} status={rollback.status} />
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
      <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: 'rgba(0,229,255,0.15)', border: '1px solid rgba(0,229,255,0.3)' }}>
        <Bot size={14} className="neon-cyan" />
      </div>
      <div className="rounded-2xl px-4 py-3 flex items-center gap-1.5"
        style={{ background: 'rgba(20,27,45,0.9)', border: '1px solid var(--border)', borderBottomLeftRadius: 4 }}>
        <div className="typing-dot" />
        <div className="typing-dot" />
        <div className="typing-dot" />
      </div>
    </div>
  )
}

export function PendingDeployBanner({ pendingDeploy }) {
  if (!pendingDeploy) return null
  return (
    <div className="mx-4 mb-2 px-3 py-2 rounded-lg flex items-center gap-2 text-xs animate-fade-in"
      style={{ background: 'rgba(0,229,255,0.08)', border: '1px solid rgba(0,229,255,0.25)' }}>
      <Clock size={12} className="neon-cyan" />
      <span style={{ color: 'var(--text-secondary)' }}>
        Waiting for GitHub URL to deploy <strong style={{ color: 'var(--cyan)' }}>{pendingDeploy.app_name}</strong>
      </span>
    </div>
  )
}
