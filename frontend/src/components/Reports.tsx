import { useEffect, useState, type ReactNode } from 'react'
import { getReports, type CandidateReport, type HiringReport, type Reports as ReportsData } from '../lib/api'
import { VERDICT } from '../lib/reports'
import EvidenceCard from './EvidenceCard'
import ScoreRow from './ScoreRow'

interface Props {
  sessionId: string | null
  onBackToTranscript: () => void
  onHome: () => void
}

type Tab = 'candidate' | 'hiring'

export default function Reports({ sessionId, onBackToTranscript, onHome }: Props) {
  const [data, setData] = useState<ReportsData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(!!sessionId)
  const [tab, setTab] = useState<Tab>('hiring')

  useEffect(() => {
    if (!sessionId) return
    let live = true
    setLoading(true)
    setError(null)
    getReports(sessionId)
      .then((r) => live && setData(r))
      .catch((e: Error) => live && setError(e.message))
      .finally(() => live && setLoading(false))
    return () => {
      live = false
    }
  }, [sessionId])

  if (!sessionId || error || (!loading && !data)) {
    return (
      <section className="step-in">
        <h2>Reports</h2>
        <div className="panel empty">
          <p>
            {!sessionId
              ? 'Open a session to see its reports.'
              : error
                ? `Couldn’t load reports: ${error}`
                : 'No reports yet.'}
          </p>
          <div className="report-actions">
            {sessionId && (
              <button type="button" className="btn" onClick={onBackToTranscript}>
                Back to transcript
              </button>
            )}
            <button type="button" className="btn btn-ghost" onClick={onHome}>
              Back to home
            </button>
          </div>
        </div>
      </section>
    )
  }

  if (loading || !data) {
    return (
      <section className="step-in">
        <h2>Reports</h2>
        <p className="muted" role="status">
          Loading your reports…
        </p>
      </section>
    )
  }

  return (
    <section className="reports step-in">
      <div className="reports-top">
        <div>
          <p className="eyebrow">Reports</p>
          <h2>Two views of the same interview</h2>
        </div>
        <button type="button" className="btn btn-ghost" onClick={onBackToTranscript}>
          Back to transcript
        </button>
      </div>

      <div role="tablist" aria-label="Report type" className="tabs">
        <button
          type="button"
          role="tab"
          id="tab-candidate"
          aria-selected={tab === 'candidate'}
          aria-controls="panel-candidate"
          className={`tab${tab === 'candidate' ? ' is-active' : ''}`}
          onClick={() => setTab('candidate')}
        >
          Candidate feedback
        </button>
        <button
          type="button"
          role="tab"
          id="tab-hiring"
          aria-selected={tab === 'hiring'}
          aria-controls="panel-hiring"
          className={`tab${tab === 'hiring' ? ' is-active' : ''}`}
          onClick={() => setTab('hiring')}
        >
          Hiring decision
        </button>
      </div>

      {tab === 'candidate' ? (
        <div role="tabpanel" id="panel-candidate" aria-labelledby="tab-candidate" key="candidate">
          <CandidateView r={data.candidate} />
        </div>
      ) : (
        <div role="tabpanel" id="panel-hiring" aria-labelledby="tab-hiring" key="hiring">
          <HiringView r={data.hiring} />
        </div>
      )}
    </section>
  )
}

function Section(props: { title: string; empty?: string; count: number; children: ReactNode }) {
  return (
    <section className="report-section">
      <h3>{props.title}</h3>
      {props.count > 0 ? (
        <div className="evidence-grid">{props.children}</div>
      ) : (
        <p className="muted">{props.empty ?? 'Nothing to show.'}</p>
      )}
    </section>
  )
}

function Unknowns({ items }: { items: string[] }) {
  return (
    <section className="report-section">
      <h3>Not enough evidence</h3>
      {items.length > 0 ? (
        <ul className="plain-list">
          {items.map((u, i) => (
            <li key={i}>{u}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">Nothing was left unclear.</p>
      )}
    </section>
  )
}

function CandidateView({ r }: { r: CandidateReport }) {
  return (
    <div className="report-stack">
      <div className="panel report-reveal">
        <h3>Your scores</h3>
        <ScoreRow scores={r.scores} />
      </div>
      <div className="panel report-reveal">
        <h3>Summary</h3>
        <p className="report-text">{r.summary}</p>
      </div>
      <Section title="Strengths" count={r.strengths.length} empty="No clear strengths were found in the transcript.">
        {r.strengths.map((s, i) => (
          <EvidenceCard key={i} title={s.point} quote={s.evidence_quote} />
        ))}
      </Section>
      <Section title="What to improve" count={r.improvements.length} empty="No improvements were flagged.">
        {r.improvements.map((s, i) => (
          <EvidenceCard key={i} title={s.point} quote={s.evidence_quote} tone="warn">
            <p className="tip">
              <strong>Try this:</strong> {s.tip}
            </p>
          </EvidenceCard>
        ))}
      </Section>
      {r.question_notes.length > 0 && (
        <Section title="Notes by question" count={r.question_notes.length}>
          {r.question_notes.map((q, i) => (
            <EvidenceCard key={i} title={q.topic_or_question} quote={q.evidence_quote}>
              <p>{q.note}</p>
            </EvidenceCard>
          ))}
        </Section>
      )}
      <div className="panel">
        <h3>Practice focus</h3>
        <p className="report-text">{r.readiness_note}</p>
      </div>
      <Unknowns items={r.unknowns} />
    </div>
  )
}

function HiringView({ r }: { r: HiringReport }) {
  const v = VERDICT[r.recommendation] ?? VERDICT.borderline
  return (
    <div className="report-stack">
      <div className={`panel verdict report-reveal tone-${v.tone}`}>
        <div>
          <p className="verdict-kicker">Recommendation</p>
          <p className="verdict-badge" aria-label={`Recommendation: ${v.label}`}>
            {v.label}
          </p>
          <p className="verdict-conf">Confidence {Math.round(r.hire_confidence)}%</p>
        </div>
        <p className="report-text verdict-fit">{r.fit_summary}</p>
      </div>
      <div className="panel report-reveal">
        <h3>Scores</h3>
        <ScoreRow scores={r.scores} />
      </div>
      <Section title="Skills with evidence" count={r.skill_evidence.length} empty="No skills were backed by a quote.">
        {r.skill_evidence.map((s, i) => (
          <EvidenceCard key={i} title={s.skill} quote={s.evidence_quote} />
        ))}
      </Section>
      <Section title="Gaps" count={r.gaps.length} empty="No gaps were found.">
        {r.gaps.map((g, i) => (
          <EvidenceCard key={i} title={g.skill_or_requirement} tone="warn">
            <p>{g.note}</p>
          </EvidenceCard>
        ))}
      </Section>
      <Section title="Red flags" count={r.red_flags.length} empty="No red flags were found.">
        {r.red_flags.map((g, i) => (
          <EvidenceCard key={i} title={g.note} quote={g.evidence_quote} tone="warn" />
        ))}
      </Section>
      <section className="report-section">
        <h3>Questions for the next round</h3>
        {r.follow_up_questions.length > 0 ? (
          <ul className="plain-list">
            {r.follow_up_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">No follow-up questions suggested.</p>
        )}
      </section>
      <Unknowns items={r.unknowns} />
      <p className="disclaimer" role="note">
        {r.disclaimer || 'This report is assistive only. A person makes the hiring decision.'}
      </p>
    </div>
  )
}
