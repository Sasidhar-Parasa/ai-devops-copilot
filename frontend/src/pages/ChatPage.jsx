import { useEffect, useRef } from 'react'
import { Bot, Cpu } from 'lucide-react'
import { useChat } from '../hooks/useChat'
import { ChatMessage, TypingIndicator, PendingDeployBanner } from '../components/chat/ChatMessage'
import { ChatInput } from '../components/chat/ChatInput'

export function ChatPage() {
  const { messages, loading, sendMessage, pendingDeploy, deployStream } = useChat()
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, deployStream.events])

  return (
    <div className="flex flex-col h-full">
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
              Real-time deployment · Docker Compose · Cloud Run
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {deployStream.running && (
            <div className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-full animate-pulse-slow"
              style={{ background: 'rgba(0,229,255,0.1)', border: '1px solid rgba(0,229,255,0.3)', color: 'var(--cyan)' }}>
              <Cpu size={10} />Deploying…
            </div>
          )}
          {pendingDeploy && !deployStream.running && (
            <div className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-full"
              style={{ background: 'rgba(255,179,0,0.1)', border: '1px solid rgba(255,179,0,0.3)', color: '#ffb300' }}>
              <Cpu size={10} />Awaiting repo URL
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className="dot dot-healthy dot-pulse" />
            <span className="text-xs neon-green font-mono">ONLINE</span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {messages.map((msg, i) => {
          const isLastDeployMsg = (
            msg.role === 'assistant' &&
            msg.intent === 'deploy' &&
            i === messages.length - 1
          )
          return (
            <ChatMessage
              key={msg.id}
              msg={msg}
              deployStream={isLastDeployMsg ? deployStream : null}
            />
          )
        })}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      <PendingDeployBanner app={pendingDeploy?.app_name || pendingDeploy} />
      <ChatInput onSend={sendMessage} loading={loading}
        pendingDeploy={pendingDeploy?.app_name || pendingDeploy} />
    </div>
  )
}
