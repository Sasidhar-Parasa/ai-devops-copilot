import { RefreshCw, LayoutDashboard, ExternalLink, CloudLightning, AlertCircle, Clock, CheckCircle, XCircle } from 'lucide-react'
import { useDashboard } from '../hooks/useDashboard'
import { LogsPanel } from '../components/dashboard/LogsPanel'
import { IncidentsSection } from '../components/dashboard/IncidentsSection'

// ── Real deployment card (no fake data) ───────────────────────────────────────
function DeploymentCard({ dep }) {
  const statusConfig = {
    success:     { icon: CheckCircle, color: '#00ff9d', label: 'Success' },
    failed:      { icon: XCircle,     color: '#ff3d57', label: 'Failed'  },
    rolled_back: { icon: AlertCircle, color: '#ffb300', label: 'Rolled Back' },
    pending:     { icon: Clock,       color: '#4a5568', label: 'Pending' },
  }
  const s = statusConfig[dep.status] || statusConfig.pending
  const Icon = s.icon
  const stages = dep.stages || []
  const ts = new Date(dep.created_at).toLocaleString([], {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })

  return (
    <div className="rounded-xl p-4 transition-all hover:scale-[1.005]"
      style={{ background: 'rgba(20,27,45,0.85)', border: `1px solid ${s.color}22` }}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
              {dep.app_name}
            </span>
            <span className="font-mono text-xs px-2 py-0.5 rounded"
              style={{ background: 'rgba(0,229,255,0.08)', color: 'var(--cyan)', border: '1px solid rgba(0,229,255,0.2)' }}>
              {dep.version}
            </span>
          </div>
          <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {ts} · {dep.environment}
            {dep.repo_url && (
              <span className="ml-2 font-mono opacity-60">
                {dep.repo_url.replace('https://github.com/', '')}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0 text-xs font-medium px-2.5 py-1 rounded-full"
          style={{ background: `${s.color}14`, border: `1px solid ${s.color}35`, color: s.color }}>
          <Icon size={11} />
          {s.label}
        </div>
      </div>

      {/* Pipeline stages */}
      {stages.length > 0 && (
        <div className="flex items-center gap-1 mb-3 overflow-x-auto">
          {stages.map((stage, i) => {
            const sc = stage.status === 'success' ? '#00ff9d'
              : stage.status === 'failed'  ? '#ff3d57' : '#4a5568'
            return (
              <div key={i} className="flex items-center flex-shrink-0">
                <div className="flex flex-col items-center gap-0.5">
                  <div className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold"
                    style={{ background: `${sc}14`, border: `1px solid ${sc}35`, color: sc }}>
                    {stage.status === 'success' ? '✓' : stage.status === 'failed' ? '✗' : '·'}
                  </div>
                  <span style={{ color: '#4a5568', fontSize: 9 }}>{stage.name}</span>
                </div>
                {i < stages.length - 1 && (
                  <div className="w-4 h-px mx-0.5" style={{ background: `${sc}40` }} />
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Live URL */}
      {dep.service_url && (
        <a href={dep.service_url} target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs font-mono neon-green hover:opacity-80 transition-opacity">
          <ExternalLink size={10} />
          {dep.service_url}
        </a>
      )}

      {/* Error */}
      {dep.error_message && (
        <div className="mt-2 text-xs font-mono px-2 py-1.5 rounded"
          style={{ background: 'rgba(255,61,87,0.08)', color: '#ff3d57', border: '1px solid rgba(255,61,87,0.2)' }}>
          {dep.error_message}
        </div>
      )}
    </div>
  )
}

function CloudRunServices({ services = [] }) {
  if (!services.length) return null
  return (
    <div>
      <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2"
        style={{ color: 'var(--text-primary)' }}>
        <CloudLightning size={14} style={{ color: 'var(--cyan)' }} />
        Live Cloud Run Services
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {services.map(svc => (
          <div key={svc.name} className="rounded-xl p-3 flex items-center justify-between"
            style={{ background: 'rgba(20,27,45,0.8)', border: `1px solid ${svc.ready ? 'rgba(0,255,157,0.2)' : 'rgba(255,61,87,0.2)'}` }}>
            <div className="flex items-center gap-2">
              <span className={`dot ${svc.ready ? 'dot-healthy dot-pulse' : 'dot-down'}`} />
              <div>
                <div className="text-sm font-mono font-medium" style={{ color: 'var(--text-primary)' }}>
                  {svc.name}
                </div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{svc.region}</div>
              </div>
            </div>
            {svc.url && (
              <a href={svc.url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs neon-cyan hover:opacity-80 transition-opacity">
                <ExternalLink size={11} />Open
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { health, deployments, logs, incidents, cloudRunServices, loading, lastRefresh, refresh } = useDashboard()
  const hasRealData = deployments.length > 0 || cloudRunServices.length > 0

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0 sticky top-0 z-10"
        style={{ borderColor: 'var(--border)', background: 'rgba(11,15,26,0.95)', backdropFilter: 'blur(12px)' }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: 'rgba(0,229,255,0.1)', border: '1px solid rgba(0,229,255,0.22)' }}>
            <LayoutDashboard size={18} className="neon-cyan" />
          </div>
          <div>
            <h1 className="font-display font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
              Operations Dashboard
            </h1>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {health?.source === 'gcp_real' ? '🟢 Live GCP data' : '🟡 Local data'}
              {lastRefresh && ` · ${lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`}
            </p>
          </div>
        </div>
        <button onClick={refresh} disabled={loading}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all hover:scale-105 disabled:opacity-50"
          style={{ background: 'rgba(0,229,255,0.07)', border: '1px solid rgba(0,229,255,0.18)', color: 'var(--cyan)' }}>
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      <div className="p-6 space-y-6">
        {loading && !health ? (
          <div className="flex items-center justify-center h-48">
            <div className="flex flex-col items-center gap-3">
              <RefreshCw size={22} className="animate-spin neon-cyan" />
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Loading…</span>
            </div>
          </div>
        ) : (
          <>
            {/* Active incidents */}
            <IncidentsSection incidents={incidents} />

            {/* Cloud Run services */}
            {cloudRunServices.length > 0 && <CloudRunServices services={cloudRunServices} />}

            {/* Deployments */}
            <div>
              <h3 className="font-display font-semibold text-sm mb-3" style={{ color: 'var(--text-primary)' }}>
                Recent Deployments
              </h3>
              {deployments.length === 0 ? (
                <div className="rounded-xl p-8 text-center"
                  style={{ border: '1px dashed rgba(255,255,255,0.07)', color: 'var(--text-secondary)' }}>
                  <div className="text-3xl mb-3">🚀</div>
                  <p className="text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    No deployments yet
                  </p>
                  <p className="text-xs">
                    Go to the chat and say{' '}
                    <span className="font-mono neon-cyan">
                      deploy https://github.com/you/myapp
                    </span>{' '}
                    to get started.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {deployments.slice(0, 8).map(dep => (
                    <DeploymentCard key={dep.id} dep={dep} />
                  ))}
                </div>
              )}
            </div>

            {/* Logs — only show if there are real logs */}
            {logs.length > 0 && <LogsPanel logs={logs} />}
          </>
        )}
      </div>
    </div>
  )
}
