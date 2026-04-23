import { useState } from 'react'
import { Terminal, Filter } from 'lucide-react'

const LEVEL_STYLE = {
  INFO:     { color: '#00e5ff', bg: 'rgba(0,229,255,0.08)',  border: 'rgba(0,229,255,0.15)'  },
  WARN:     { color: '#ffb300', bg: 'rgba(255,179,0,0.08)',  border: 'rgba(255,179,0,0.2)'   },
  ERROR:    { color: '#ff3d57', bg: 'rgba(255,61,87,0.1)',   border: 'rgba(255,61,87,0.25)'  },
  CRITICAL: { color: '#ff3d57', bg: 'rgba(255,61,87,0.15)',  border: 'rgba(255,61,87,0.35)'  },
  DEBUG:    { color: '#4a5568', bg: 'rgba(255,255,255,0.03)', border: 'rgba(255,255,255,0.06)'},
}

const FILTERS = ['ALL', 'INFO', 'WARN', 'ERROR', 'CRITICAL']

export function LogsPanel({ logs = [] }) {
  const [filter, setFilter] = useState('ALL')
  const displayed = filter === 'ALL' ? logs : logs.filter(l => l.level === filter)

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3"
        style={{ background: 'rgba(20,27,45,0.95)', borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <Terminal size={14} style={{ color: 'var(--cyan)' }} />
          <span className="font-display font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
            System Logs
          </span>
          <span className="text-xs font-mono px-2 py-0.5 rounded"
            style={{ background: 'rgba(0,229,255,0.1)', color: 'var(--cyan)', border: '1px solid rgba(0,229,255,0.2)' }}>
            {displayed.length}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Filter size={11} style={{ color: 'var(--text-muted)' }} />
          {FILTERS.map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className="text-xs px-2 py-0.5 rounded transition-all"
              style={filter === f
                ? { background: LEVEL_STYLE[f]?.bg || 'rgba(0,229,255,0.1)', color: LEVEL_STYLE[f]?.color || 'var(--cyan)', border: `1px solid ${LEVEL_STYLE[f]?.border || 'rgba(0,229,255,0.2)'}` }
                : { color: 'var(--text-muted)', background: 'transparent' }}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Log entries */}
      <div className="overflow-y-auto font-mono" style={{ maxHeight: 300, background: 'rgba(8,12,20,0.95)' }}>
        {displayed.length === 0 ? (
          <div className="px-4 py-8 text-center text-xs" style={{ color: 'var(--text-muted)' }}>No logs match this filter</div>
        ) : (
          displayed.map((log, i) => {
            const s = LEVEL_STYLE[log.level] || LEVEL_STYLE.DEBUG
            const ts = new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            return (
              <div key={log.id || i}
                className="flex gap-3 px-4 py-1.5 border-b text-xs hover:bg-white/[0.02] transition-colors"
                style={{ borderColor: 'rgba(255,255,255,0.03)' }}>
                <span className="flex-shrink-0" style={{ color: '#4a5568' }}>{ts}</span>
                <span className="flex-shrink-0 px-1.5 rounded text-xs font-bold"
                  style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}`, fontSize: 10, lineHeight: '18px' }}>
                  {log.level}
                </span>
                <span className="flex-shrink-0" style={{ color: '#b388ff', minWidth: 100 }}>{log.service}</span>
                <span className="flex-1 truncate" style={{ color: 'var(--text-secondary)' }}>{log.message}</span>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
