import { Activity, Cpu, MemoryStick, Gauge } from 'lucide-react'

function MiniBar({ value, color, max = 100 }) {
  const pct = Math.min((value / max) * 100, 100)
  const isHigh = pct > 70
  return (
    <div className="w-full h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
      <div className="h-full rounded-full transition-all duration-700"
        style={{ width: `${pct}%`, background: isHigh ? '#ff3d57' : color, boxShadow: `0 0 4px ${isHigh ? '#ff3d57' : color}60` }} />
    </div>
  )
}

function MetricRow({ icon: Icon, label, value, unit, color }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="flex items-center gap-1.5" style={{ color: 'var(--text-secondary)' }}>
        <Icon size={11} />
        <span className="text-xs">{label}</span>
      </div>
      <span className="text-xs font-mono font-semibold" style={{ color }}>
        {typeof value === 'number' ? value.toFixed(1) : value}{unit}
      </span>
    </div>
  )
}

export function ServiceHealthGrid({ services = [] }) {
  return (
    <div>
      <h3 className="font-display font-semibold text-sm mb-3" style={{ color: 'var(--text-primary)' }}>
        Service Health
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {services.map(svc => {
          const isHealthy = svc.status === 'healthy'
          const isDegraded = svc.status === 'degraded'
          const dotClass = isHealthy ? 'dot-healthy' : isDegraded ? 'dot-degraded' : 'dot-down'
          const accentColor = isHealthy ? '#00ff9d' : isDegraded ? '#ffb300' : '#ff3d57'

          return (
            <div key={svc.service} className="rounded-xl p-3 transition-all duration-200 hover:scale-[1.01]"
              style={{ background: 'rgba(20,27,45,0.8)', border: `1px solid ${isHealthy ? 'var(--border)' : accentColor + '30'}` }}>
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`dot ${dotClass} ${isHealthy ? 'dot-pulse' : ''}`} />
                  <span className="font-mono text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                    {svc.service}
                  </span>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{ background: accentColor + '18', color: accentColor, border: `1px solid ${accentColor}30` }}>
                  {svc.uptime_pct}%
                </span>
              </div>

              {/* Metrics */}
              <div className="space-y-2">
                <div>
                  <MetricRow icon={Cpu} label="CPU" value={svc.cpu_pct} unit="%" color={svc.cpu_pct > 70 ? '#ff3d57' : '#00e5ff'} />
                  <MiniBar value={svc.cpu_pct} color="#00e5ff" />
                </div>
                <div>
                  <MetricRow icon={MemoryStick} label="Memory" value={svc.memory_pct} unit="%" color={svc.memory_pct > 80 ? '#ffb300' : '#b388ff'} />
                  <MiniBar value={svc.memory_pct} color="#b388ff" />
                </div>
                <div className="flex justify-between pt-1">
                  <div className="flex items-center gap-1" style={{ color: 'var(--text-secondary)' }}>
                    <Activity size={10} />
                    <span className="text-xs">{svc.request_rate}/s</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Gauge size={10} style={{ color: svc.latency_p99_ms > 500 ? '#ff3d57' : '#00e5ff' }} />
                    <span className="text-xs font-mono" style={{ color: svc.latency_p99_ms > 500 ? '#ff3d57' : 'var(--text-secondary)' }}>
                      {svc.latency_p99_ms.toFixed(0)}ms
                    </span>
                  </div>
                  <span className="text-xs font-mono" style={{ color: svc.error_rate > 5 ? '#ff3d57' : '#4a5568' }}>
                    {svc.error_rate.toFixed(1)}% err
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
