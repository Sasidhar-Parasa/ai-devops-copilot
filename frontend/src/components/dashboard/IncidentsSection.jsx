import { AlertTriangle, AlertCircle, Info, CheckCircle } from 'lucide-react'

const SEV = {
  critical: { icon: AlertCircle,  color: '#ff3d57', bg: 'rgba(255,61,87,0.1)',  border: 'rgba(255,61,87,0.3)'  },
  high:     { icon: AlertTriangle, color: '#ffb300', bg: 'rgba(255,179,0,0.08)', border: 'rgba(255,179,0,0.25)' },
  medium:   { icon: Info,          color: '#00e5ff', bg: 'rgba(0,229,255,0.08)', border: 'rgba(0,229,255,0.2)'  },
  low:      { icon: Info,          color: '#b388ff', bg: 'rgba(179,136,255,0.08)', border: 'rgba(179,136,255,0.2)' },
}

export function IncidentsSection({ incidents = [] }) {
  const open = incidents.filter(i => i.status !== 'resolved')
  const resolved = incidents.filter(i => i.status === 'resolved').slice(0, 2)

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-display font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
          Active Incidents
        </h3>
        {open.length > 0 && (
          <span className="text-xs px-2 py-0.5 rounded-full font-medium animate-pulse-slow"
            style={{ background: 'rgba(255,61,87,0.15)', color: '#ff3d57', border: '1px solid rgba(255,61,87,0.3)' }}>
            {open.length} open
          </span>
        )}
      </div>

      <div className="space-y-2">
        {open.length === 0 && (
          <div className="rounded-xl p-4 flex items-center gap-3"
            style={{ background: 'rgba(0,255,157,0.06)', border: '1px solid rgba(0,255,157,0.2)' }}>
            <CheckCircle size={16} style={{ color: '#00ff9d' }} />
            <span className="text-sm" style={{ color: '#00ff9d' }}>All clear — no active incidents</span>
          </div>
        )}

        {open.map(inc => {
          const s = SEV[inc.severity] || SEV.medium
          const Icon = s.icon
          return (
            <div key={inc.id} className="rounded-xl p-3"
              style={{ background: s.bg, border: `1px solid ${s.border}` }}>
              <div className="flex items-start gap-3">
                <Icon size={15} style={{ color: s.color, flexShrink: 0, marginTop: 1 }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{inc.title}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full capitalize"
                      style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>
                      {inc.severity}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full capitalize ml-auto"
                      style={{ color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.04)' }}>
                      {inc.status}
                    </span>
                  </div>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{inc.description}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                    <span className="font-mono">{inc.service}</span>
                    <span>{new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    {inc.root_cause && (
                      <span className="text-xs" style={{ color: '#ffb300' }}>🔍 {inc.root_cause.slice(0, 60)}…</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )
        })}

        {resolved.map(inc => (
          <div key={inc.id} className="rounded-xl p-3 opacity-50"
            style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="flex items-center gap-3">
              <CheckCircle size={13} style={{ color: '#00ff9d' }} />
              <span className="text-xs line-through" style={{ color: 'var(--text-secondary)' }}>{inc.title}</span>
              <span className="text-xs ml-auto" style={{ color: '#00ff9d' }}>resolved</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
