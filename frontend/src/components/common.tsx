import type { ReactNode } from 'react'
import { Database } from 'lucide-react'
import { colors, states } from '../api'
import type { Sentiment } from '../api'

export function Badge({ state }: { state: Sentiment }) {
  return (
    <span className={`badge ${state}`}>
      <i />
      {state}
    </span>
  )
}

export function Empty({
  title,
  children,
  icon = <Database size={25} />,
}: {
  title: string
  children: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">{icon}</span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  )
}

export function Legend() {
  return (
    <div className="legend">
      {states.map((state) => (
        <span key={state}>
          <i style={{ background: colors[state] }} />
          {state}
        </span>
      ))}
    </div>
  )
}
export function Metric({
  label,
  value,
  detail,
  icon,
  accent = false,
}: {
  label: string
  value: string
  detail: string
  icon: ReactNode
  accent?: boolean
}) {
  return (
    <div className={`metric-card ${accent ? 'accent' : ''}`}>
      <div className="metric-label">
        {label}
        <span>{icon}</span>
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  )
}
