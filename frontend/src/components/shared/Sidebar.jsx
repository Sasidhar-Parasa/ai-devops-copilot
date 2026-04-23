import { MessageSquare, LayoutDashboard, Cpu, Zap } from 'lucide-react'

const NAV = [
  { id: 'chat',      icon: MessageSquare,  label: 'Copilot Chat' },
  { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
]

export function Sidebar({ active, onNav, health }) {
  const overall = health?.overall || 'loading'
  return (
    <aside className="w-16 lg:w-56 glass border-r flex flex-col" style={{ borderColor: 'var(--border)' }}>
      {/* Logo */}
      <div className="px-3 lg:px-5 py-5 border-b flex items-center gap-3" style={{ borderColor: 'var(--border)' }}>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: 'linear-gradient(135deg, rgba(0,229,255,0.3), rgba(179,136,255,0.3))', border: '1px solid rgba(0,229,255,0.3)' }}>
          <Cpu size={16} className="neon-cyan" />
        </div>
        <div className="hidden lg:block">
          <div className="font-display font-bold text-sm" style={{ color: 'var(--text-primary)' }}>AI DevOps</div>
          <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Copilot</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-2 lg:p-3 space-y-1">
        {NAV.map(({ id, icon: Icon, label }) => (
          <button key={id} onClick={() => onNav(id)}
            className={`w-full flex items-center gap-3 px-2 lg:px-3 py-2.5 rounded-lg transition-all duration-200 text-left ${
              active === id
                ? 'text-white'
                : 'hover:bg-white/5'
            }`}
            style={active === id ? {
              background: 'rgba(0,229,255,0.1)',
              border: '1px solid rgba(0,229,255,0.2)',
              color: 'var(--cyan)',
            } : { color: 'var(--text-secondary)' }}>
            <Icon size={16} className="flex-shrink-0" />
            <span className="hidden lg:block text-sm font-medium">{label}</span>
          </button>
        ))}
      </nav>

      {/* System status pill */}
      <div className="p-3 border-t hidden lg:block" style={{ borderColor: 'var(--border)' }}>
        <div className="rounded-lg p-3" style={{ background: 'rgba(0,0,0,0.2)' }}>
          <div className="flex items-center gap-2 mb-1">
            <span className={`dot ${overall === 'healthy' ? 'dot-healthy dot-pulse' : overall === 'degraded' ? 'dot-degraded' : 'dot-down'}`} />
            <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>System</span>
          </div>
          <div className={`text-xs font-mono font-semibold ${overall === 'healthy' ? 'neon-green' : overall === 'degraded' ? 'neon-amber' : 'neon-red'}`}>
            {overall.toUpperCase()}
          </div>
          {health && (
            <div className="text-xs mt-1" style={{ color: 'var(--text-muted)', fontSize: 11 }}>
              {health.active_incidents} incident{health.active_incidents !== 1 ? 's' : ''}
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
