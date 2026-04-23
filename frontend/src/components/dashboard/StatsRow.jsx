import { TrendingUp, TrendingDown, Minus, Server, Rocket, ShieldAlert, Activity } from 'lucide-react'

function StatCard({ icon: Icon, label, value, sub, color, trend }) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = trend === 'up' ? '#00ff9d' : trend === 'down' ? '#ff3d57' : '#4a5568'

  return (
    <div className="rounded-xl p-4 transition-all duration-300 hover:scale-[1.02]"
      style={{ background: 'rgba(20,27,45,0.8)', border: `1px solid ${color}25` }}>
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ background: color + '18', border: `1px solid ${color}35` }}>
          <Icon size={16} style={{ color }} />
        </div>
        {trend && (
          <TrendIcon size={14} style={{ color: trendColor }} />
        )}
      </div>
      <div className="font-display font-bold text-2xl mb-0.5" style={{ color: 'var(--text-primary)' }}>
        {value}
      </div>
      <div className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</div>
      {sub && <div className="text-xs mt-1" style={{ color: '#4a5568' }}>{sub}</div>}
    </div>
  )
}

export function StatsRow({ health, deployments, incidents }) {
  const totalDeps = deployments.length
  const successDeps = deployments.filter(d => d.status === 'success').length
  const successRate = totalDeps > 0 ? Math.round((successDeps / totalDeps) * 100) : 100
  const openIncidents = incidents.filter(i => i.status !== 'resolved').length

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard
        icon={Server}
        label="System Status"
        value={health?.overall === 'healthy' ? 'Healthy' : health?.overall === 'degraded' ? 'Degraded' : '—'}
        sub={`${health?.services?.length || 0} services monitored`}
        color={health?.overall === 'healthy' ? '#00ff9d' : '#ffb300'}
        trend={health?.overall === 'healthy' ? 'up' : 'down'}
      />
      <StatCard
        icon={Rocket}
        label="Deploy Success"
        value={`${successRate}%`}
        sub={`${successDeps}/${totalDeps} deployments`}
        color="#00e5ff"
        trend={successRate > 80 ? 'up' : 'down'}
      />
      <StatCard
        icon={ShieldAlert}
        label="Open Incidents"
        value={openIncidents}
        sub={openIncidents === 0 ? 'All clear!' : `${openIncidents} need attention`}
        color={openIncidents === 0 ? '#00ff9d' : '#ff3d57'}
        trend={openIncidents === 0 ? 'up' : 'down'}
      />
      <StatCard
        icon={Activity}
        label="Avg Latency"
        value={health?.services ? `${Math.round(health.services.reduce((a, s) => a + s.latency_p99_ms, 0) / health.services.length)}ms` : '—'}
        sub="p99 across all services"
        color="#b388ff"
        trend="neutral"
      />
    </div>
  )
}
