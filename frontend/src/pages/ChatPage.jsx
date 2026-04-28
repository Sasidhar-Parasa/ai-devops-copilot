import { useEffect, useRef } from 'react'
import { Bot, Cpu } from 'lucide-react'
import { useChat } from '../hooks/useChat'
import { ChatMessage, TypingIndicator, PendingDeployBanner } from '../components/chat/ChatMessage'
import { ChatInput } from '../components/chat/ChatInput'

export function ChatPage() {
  const { messages, loading, sendMessage, pendingDeploy } = useChat()
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0"
        style={{ borderColor: 'var(--border)', background: 'rgba(11,15,26,0.6)' }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: 'rgba(0,229,255,0.1)', border: '1px solid rgba(0,229,255,0.22)' }}>
            <Bot size={18} className="neon-cyan" />
          </div>
          <div>
            <h1 className="font-display font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
              DevOps Copilot
            </h1>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Powered by Groq llama3-70b · 6 specialized agents
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {pendingDeploy && (
            <div className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-full"
              style={{ background: 'rgba(0,229,255,0.08)', border: '1px solid rgba(0,229,255,0.25)', color: 'var(--cyan)' }}>
              <Cpu size={10} />
              Waiting for repo URL
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className="dot dot-healthy dot-pulse" />
            <span className="text-xs neon-green font-mono">ONLINE</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {messages.map(msg => (
          <ChatMessage key={msg.id} msg={msg} />
        ))}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      <PendingDeployBanner app={pendingDeploy?.app_name || pendingDeploy} />
      <ChatInput onSend={sendMessage} loading={loading} pendingDeploy={pendingDeploy?.app_name || pendingDeploy} />
    </div>
  )
}
