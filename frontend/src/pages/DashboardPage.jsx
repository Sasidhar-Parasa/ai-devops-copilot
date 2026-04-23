import { RefreshCw, LayoutDashboard, CloudLightning, ExternalLink } from 'lucide-react'
import { useDashboard } from '../hooks/useDashboard'
import { StatsRow } from '../components/dashboard/StatsRow'
import { PipelineCard } from '../components/dashboard/PipelineCard'
import { ServiceHealthGrid } from '../components/dashboard/ServiceHealthGrid'
import { LogsPanel } from '../components/dashboard/LogsPanel'
import { IncidentsSection } from '../components/dashboard/IncidentsSection'

function CloudRunServices({ services = [] }) {
  if (!services.length) return null
  return (
    <div>
      <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
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
                <div className="text-sm font-mono font-medium" style={{ color: 'var(--text-primary)' }}>{svc.name}</div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{svc.region}</div>
              </div>
            </div>
            {svc.url && (
              <a href={svc.url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs neon-cyan hover:opacity-80 transition-opacity">
                <ExternalLink size={11} />
                <span>Open</span>
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

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Sticky header */}
      <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0 sticky top-0 z-10"
        style={{ borderColor: 'var(--border)', background: 'rgba(11,15,26,0.95)', backdropFilter: 'blur(12px)' }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: 'rgba(0,229,255,0.12)', border: '1px solid rgba(0,229,255,0.25)' }}>
            <LayoutDashboard size={18} className="neon-cyan" />
          </div>
          <div>
            <h1 className="font-display font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
              Operations Dashboard
            </h1>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {health?.source === 'gcp_real' ? '🟢 Live GCP data' : '🟡 Simulated data'}
              {lastRefresh && ` · Updated ${lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`}
            </p>
          </div>
        </div>
        <button onClick={refresh} disabled={loading}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all hover:scale-105 disabled:opacity-50"
          style={{ background: 'rgba(0,229,255,0.08)', border: '1px solid rgba(0,229,255,0.2)', color: 'var(--cyan)' }}>
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      <div className="p-6 space-y-6">
        {loading && !health ? (
          <div className="flex items-center justify-center h-40">
            <div className="flex flex-col items-center gap-3">
              <RefreshCw size={24} className="animate-spin neon-cyan" />
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Loading dashboard…</span>
            </div>
          </div>
        ) : (
          <>
            <StatsRow health={health} deployments={deployments} incidents={incidents} />
            <IncidentsSection incidents={incidents} />
            {cloudRunServices.length > 0 && <CloudRunServices services={cloudRunServices} />}

            <div>
              <h3 className="font-display font-semibold text-sm mb-3" style={{ color: 'var(--text-primary)' }}>
                Recent Deployments
              </h3>
              <div className="space-y-3">
                {deployments.length === 0 ? (
                  <div className="rounded-xl p-6 text-center text-sm"
                    style={{ color: 'var(--text-secondary)', border: '1px dashed rgba(255,255,255,0.08)' }}>
                    No deployments yet. Try: <span className="font-mono neon-cyan">deploy https://github.com/you/myapp</span>
                  </div>
                ) : (
                  deployments.slice(0, 5).map(dep => <PipelineCard key={dep.id} deployment={dep} />)
                )}
              </div>
            </div>

            {health?.services && <ServiceHealthGrid services={health.services} />}
            <LogsPanel logs={logs} />
          </>
        )}
      </div>
    </div>
  )
}
