/**
 * DeploymentStream — live deployment log panel embedded in the chat bubble.
 * Looks like GitHub Actions / Railway / Vercel logs.
 */
import { useEffect, useRef } from 'react'
import { CheckCircle, XCircle, Loader, Info, ExternalLink, Zap } from 'lucide-react'
import { STAGE_LABELS } from '../../hooks/useDeployStream'

// ── Status config ─────────────────────────────────────────────────────────────
const STATUS = {
  running: { icon: Loader,      color: '#00e5ff', spin: true,  label: 'Running'  },
  success: { icon: CheckCircle, color: '#00ff9d', spin: false, label: 'Done'     },
  error:   { icon: XCircle,     color: '#ff3d57', spin: false, label: 'Failed'   },
  info:    { icon: Info,        color: '#ffb300', spin: false, label: 'Info'     },
}

function EventRow({ evt, isActive }) {
  const s   = STATUS[evt.status] || STATUS.info
  const Icon = s.icon
  const ts  = new Date(evt.timestamp || Date.now()).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })

  return (
    <div
      className="flex items-start gap-2.5 px-3 py-2 text-xs transition-all"
      style={{
        background:   isActive ? 'rgba(0,229,255,0.05)' : 'transparent',
        borderLeft:   isActive ? `2px solid ${s.color}` : '2px solid transparent',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      {/* Icon */}
      <div className="flex-shrink-0 mt-0.5">
        <Icon
          size={13}
          style={{ color: s.color }}
          className={s.spin ? 'animate-spin' : ''}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono font-medium" style={{ color: s.color }}>
            {STAGE_LABELS[evt.stage] || evt.stage}
          </span>
          <span
            className="px-1.5 py-0.5 rounded text-[10px] font-medium"
            style={{
              background: `${s.color}18`,
              color:       s.color,
              border:     `1px solid ${s.color}35`,
            }}
          >
            {s.label}
          </span>
          <span className="ml-auto font-mono" style={{ color: '#4a5568', fontSize: 10 }}>
            {ts}
          </span>
        </div>
        {evt.message && (
          <p className="mt-0.5" style={{ color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {evt.message}
          </p>
        )}
        {/* Extra data badges */}
        {evt.data?.framework && (
          <span
            className="inline-block mt-1 px-2 py-0.5 rounded font-mono text-[10px]"
            style={{ background: 'rgba(179,136,255,0.15)', color: '#b388ff', border: '1px solid rgba(179,136,255,0.3)' }}
          >
            {evt.data.framework}
          </span>
        )}
        {evt.data?.services && evt.data.services.length > 0 && (
          <div className="mt-1 flex gap-1 flex-wrap">
            {evt.data.services.map(s => (
              <span
                key={s}
                className="px-2 py-0.5 rounded font-mono text-[10px]"
                style={{ background: 'rgba(0,229,255,0.1)', color: 'var(--cyan)', border: '1px solid rgba(0,229,255,0.2)' }}
              >
                {s}
              </span>
            ))}
          </div>
        )}
        {evt.data?.strategy && evt.status === 'success' && (
          <span className="mt-1 inline-block text-[10px]" style={{ color: '#4a5568' }}>
            strategy: {evt.data.strategy}
          </span>
        )}
      </div>
    </div>
  )
}

function ActivePulse({ stageName }) {
  if (!stageName) return null
  return (
    <div
      className="flex items-center gap-2 px-3 py-2"
      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
    >
      <Loader size={13} className="animate-spin" style={{ color: 'var(--cyan)' }} />
      <span className="text-xs font-mono" style={{ color: 'var(--cyan)' }}>
        {STAGE_LABELS[stageName] || stageName}…
      </span>
      <span className="flex gap-0.5 ml-1">
        {[0, 1, 2].map(i => (
          <span
            key={i}
            className="w-1 h-1 rounded-full"
            style={{
              background: 'var(--cyan)',
              animation: `bounce 1.2s ${i * 0.2}s ease-in-out infinite`,
              opacity:    0.7,
            }}
          />
        ))}
      </span>
    </div>
  )
}

// ── Final result banner ───────────────────────────────────────────────────────

function ResultBanner({ result }) {
  if (!result) return null
  const ok = result.status === 'success'

  return (
    <div
      className="px-3 py-3"
      style={{
        background:  ok ? 'rgba(0,255,157,0.07)' : 'rgba(255,61,87,0.07)',
        borderTop:  `1px solid ${ok ? 'rgba(0,255,157,0.2)' : 'rgba(255,61,87,0.2)'}`,
      }}
    >
      {ok ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <CheckCircle size={14} style={{ color: '#00ff9d' }} />
            <span className="text-sm font-semibold neon-green">Deployment Successful!</span>
          </div>
          {result.service_url && (
            <a
              href={result.service_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs font-mono neon-cyan hover:opacity-80 transition-opacity"
            >
              <ExternalLink size={11} />
              {result.service_url}
            </a>
          )}
          {result.total_seconds && (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Completed in {result.total_seconds}s
            </p>
          )}
        </div>
      ) : (
        <div className="flex items-start gap-2">
          <XCircle size={14} style={{ color: '#ff3d57', flexShrink: 0, marginTop: 1 }} />
          <div>
            <p className="text-sm font-semibold neon-red">Deployment Failed</p>
            {result.error && (
              <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                {result.error}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function DeploymentStream({ events, active, result, running, repoUrl }) {
  const bottomRef = useRef(null)

  // Auto-scroll to bottom as events arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events, active])

  if (!running && events.length === 0 && !result) return null

  return (
    <div
      className="mt-3 rounded-xl overflow-hidden text-xs"
      style={{ border: '1px solid rgba(0,229,255,0.18)', background: 'rgba(6,10,20,0.95)' }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,229,255,0.05)' }}
      >
        <Zap size={12} style={{ color: 'var(--cyan)' }} />
        <span className="font-mono font-semibold neon-cyan">Deployment Pipeline</span>
        {repoUrl && (
          <span className="ml-auto font-mono opacity-50 truncate max-w-[180px]" style={{ color: 'var(--text-muted)' }}>
            {repoUrl.replace('https://github.com/', '')}
          </span>
        )}
        {running && (
          <span
            className="flex-shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium ml-1"
            style={{ background: 'rgba(0,229,255,0.12)', color: 'var(--cyan)', border: '1px solid rgba(0,229,255,0.25)' }}
          >
            LIVE
          </span>
        )}
      </div>

      {/* Events log */}
      <div className="overflow-y-auto" style={{ maxHeight: 340 }}>
        {events.map((evt, i) => (
          <EventRow
            key={`${evt.stage}-${evt.status}-${i}`}
            evt={evt}
            isActive={active === evt.stage && evt.status === 'running'}
          />
        ))}
        {running && active && (
          <ActivePulse stageName={active} />
        )}
        <div ref={bottomRef} />
      </div>

      {/* Result banner */}
      <ResultBanner result={result} />
    </div>
  )
}
