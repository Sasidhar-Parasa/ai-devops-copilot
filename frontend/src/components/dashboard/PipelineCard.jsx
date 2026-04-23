import { CheckCircle, XCircle, Clock, Loader, Hammer, FlaskConical, Rocket } from 'lucide-react'

const STAGE_META = {
  Build:    { icon: Hammer,        color: '#00e5ff' },
  Test:     { icon: FlaskConical,  color: '#b388ff' },
  Deploy:   { icon: Rocket,        color: '#00ff9d' },
  Rollback: { icon: Clock,         color: '#ffb300' },
}

const STATUS_CONFIG = {
  success:      { icon: CheckCircle, color: '#00ff9d', label: 'Success' },
  failed:       { icon: XCircle,     color: '#ff3d57', label: 'Failed'  },
  pending:      { icon: Clock,       color: '#4a5568', label: 'Pending' },
  deploying:    { icon: Loader,      color: '#00e5ff', label: 'Running' },
  building:     { icon: Loader,      color: '#00e5ff', label: 'Building'},
  testing:      { icon: Loader,      color: '#b388ff', label: 'Testing' },
  rolled_back:  { icon: CheckCircle, color: '#ffb300', label: 'Rolled Back' },
}

function PipelineStage({ stage, isLast }) {
  const meta = STAGE_META[stage.name] || STAGE_META.Build
  const status = STATUS_CONFIG[stage.status] || STATUS_CONFIG.pending
  const StageIcon = meta.icon
  const StatusIcon = status.icon
  const isRunning = ['deploying','building','testing'].includes(stage.status)

  return (
    <div className="flex items-center">
      <div className="flex flex-col items-center gap-2">
        {/* Icon circle */}
        <div className="relative w-12 h-12 rounded-xl flex items-center justify-center transition-all"
          style={{
            background: stage.status === 'pending' ? 'rgba(255,255,255,0.03)' : `${meta.color}18`,
            border: `1px solid ${stage.status === 'pending' ? 'rgba(255,255,255,0.08)' : meta.color + '40'}`,
          }}>
          <StageIcon size={20} style={{ color: stage.status === 'pending' ? '#4a5568' : meta.color }} />
          {/* Status badge */}
          <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center"
            style={{ background: 'var(--bg-card)', border: `1px solid ${status.color}` }}>
            <StatusIcon size={10} style={{ color: status.color }}
              className={isRunning ? 'animate-spin' : ''} />
          </div>
        </div>
        <span className="text-xs font-medium" style={{ color: stage.status === 'pending' ? '#4a5568' : 'var(--text-secondary)' }}>
          {stage.name}
        </span>
        {stage.duration_seconds && (
          <span className="text-xs font-mono" style={{ color: '#4a5568' }}>{stage.duration_seconds}s</span>
        )}
      </div>
      {/* Connector */}
      {!isLast && (
        <div className="flex-1 h-px mx-3 relative overflow-hidden" style={{ minWidth: 24 }}>
          <div className="absolute inset-0" style={{ background: stage.status === 'success' ? `linear-gradient(90deg, ${meta.color}60, rgba(255,255,255,0.1))` : 'rgba(255,255,255,0.06)' }} />
        </div>
      )}
    </div>
  )
}

export function PipelineCard({ deployment }) {
  if (!deployment) return null
  const stages = deployment.stages || []
  const overallStatus = STATUS_CONFIG[deployment.status] || STATUS_CONFIG.pending
  const OverallIcon = overallStatus.icon

  return (
    <div className="rounded-xl p-4" style={{ background: 'rgba(20,27,45,0.8)', border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-display font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
              {deployment.app_name}
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded"
              style={{ background: 'rgba(0,229,255,0.1)', color: 'var(--cyan)', border: '1px solid rgba(0,229,255,0.2)' }}>
              {deployment.version}
            </span>
          </div>
          <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            {deployment.environment} · {new Date(deployment.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full"
          style={{ background: overallStatus.color + '18', border: `1px solid ${overallStatus.color}40`, color: overallStatus.color }}>
          <OverallIcon size={11} className={['deploying','building','testing'].includes(deployment.status) ? 'animate-spin' : ''} />
          {overallStatus.label}
        </div>
      </div>

      {/* Pipeline visualization */}
      {stages.length > 0 && (
        <div className="flex items-center py-2">
          {stages.map((stage, i) => (
            <PipelineStage key={i} stage={stage} isLast={i === stages.length - 1} />
          ))}
        </div>
      )}

      {deployment.error_message && (
        <div className="mt-3 text-xs px-3 py-2 rounded-lg font-mono"
          style={{ background: 'rgba(255,61,87,0.1)', border: '1px solid rgba(255,61,87,0.25)', color: '#ff3d57' }}>
          ⚠ {deployment.error_message}
        </div>
      )}
    </div>
  )
}
