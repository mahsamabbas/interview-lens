import type { ReactNode } from 'react'

interface Props {
  title: string
  quote?: string
  children?: ReactNode
  tone?: 'default' | 'warn'
}

export default function EvidenceCard({ title, quote, children, tone = 'default' }: Props) {
  return (
    <article className={`evidence-card${tone === 'warn' ? ' is-warn' : ''}`}>
      <h4>{title}</h4>
      {children && <div className="evidence-body">{children}</div>}
      {quote && (
        <blockquote className="evidence-quote">
          <span className="quote-label">From the interview</span>
          “{quote}”
        </blockquote>
      )}
    </article>
  )
}
