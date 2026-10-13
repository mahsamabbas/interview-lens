import { useEffect, useState } from 'react'
import { listSessions, type SessionSummary } from '../lib/api'

interface Props {
  onNew: () => void
  onOpen: (id: string) => void
}

const SOURCE_LABEL: Record<string, string> = {
  sample_video: 'Sample video',
  upload: 'Uploaded recording',
  paste: 'Pasted transcript',
}

function fmt(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export default function Home({ onNew, onOpen }: Props) {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    listSessions()
      .then((s) => live && setSessions(s))
      .catch((e: Error) => live && setError(e.message))
    return () => {
      live = false
    }
  }, [])

  return (
    <section className="step-in home">
      <div className="home-hero">
        <h1 className="wordmark">
          Interview<span>Lens</span>
        </h1>
        <p className="tagline">Dual feedback from one interview</p>
        <p className="sub">
          Add a job description and a recording. Get a candidate-friendly review and a hiring
          decision brief — both from the same conversation.
        </p>
        <button type="button" className="btn" onClick={onNew}>
          New session
        </button>
      </div>

      <div className="recent">
        <h2>Recent sessions</h2>
        {error && (
          <p className="notice" role="alert">
            Can’t reach the InterviewLens server ({error}). Start the API on port 8004, then reload.
          </p>
        )}
        {!error && sessions === null && <p className="muted">Loading sessions…</p>}
        {sessions?.length === 0 && (
          <div className="panel empty">
            <p>No sessions yet. Start your first review.</p>
            <button type="button" className="btn btn-ghost" onClick={onNew}>
              New session
            </button>
          </div>
        )}
        {sessions && sessions.length > 0 && (
          <ul className="recent-list">
            {sessions.map((s) => (
              <li key={s.id}>
                <button type="button" className="recent-item" onClick={() => onOpen(s.id)}>
                  <span className="recent-title">{s.title || 'Untitled session'}</span>
                  <span className="recent-meta">
                    {s.source_type ? SOURCE_LABEL[s.source_type] : 'No source yet'} ·{' '}
                    {fmt(s.updated_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
