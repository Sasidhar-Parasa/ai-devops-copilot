import { useState } from 'react'
import { Sidebar } from './components/shared/Sidebar'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { useDashboard } from './hooks/useDashboard'

export default function App() {
  const [page, setPage] = useState('chat')
  const { health } = useDashboard()

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
      {/* Background grid effect */}
      <div className="fixed inset-0 pointer-events-none" style={{
        backgroundImage: `
          linear-gradient(rgba(0,229,255,0.015) 1px, transparent 1px),
          linear-gradient(90deg, rgba(0,229,255,0.015) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
      }} />

      {/* Glow orbs */}
      <div className="fixed pointer-events-none" style={{ top: '-10%', left: '20%', width: 400, height: 400, background: 'radial-gradient(circle, rgba(0,229,255,0.04) 0%, transparent 70%)', borderRadius: '50%' }} />
      <div className="fixed pointer-events-none" style={{ bottom: '10%', right: '15%', width: 300, height: 300, background: 'radial-gradient(circle, rgba(179,136,255,0.05) 0%, transparent 70%)', borderRadius: '50%' }} />

      {/* Sidebar */}
      <Sidebar active={page} onNav={setPage} health={health} />

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0 relative z-10">
        {page === 'chat' && <ChatPage />}
        {page === 'dashboard' && <DashboardPage />}
      </main>
    </div>
  )
}
