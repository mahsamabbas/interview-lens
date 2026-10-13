import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getSession,
  patchTranscript,
  pollJob,
  startAnalyze,
  startTranscribe,
  type Job,
  type Segment,
  type Speaker,
} from '../lib/api'
import { jobStatusMessage } from '../lib/jobCopy'
import { canAnalyze, formatMs, nextSpeaker, toSegmentIn } from '../lib/transcript'

interface Props {
  sessionId: string
  onBack: () => void
  onAnalyzed: () => void
}

const SPEAKER_LABEL: Record<Speaker, string> = {
  interviewer: 'Interviewer',
  candidate: 'Candidate',
  unknown: 'Unknown',
}

export default function TranscriptStudio({ sessionId, onBack, onAnalyzed }: Props) {
  const [segments, setSegments] = useState<Segment[]>([])
  const [jd, setJd] = useState('')
  const [hasMedia, setHasMedia] = useState(false)
  const [loading, setLoading] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [job, setJob] = useState<{ kind: 'transcribe' | 'analyze'; status: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [savedNote, setSavedNote] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const busy = job !== null && job.status !== 'ready' && job.status !== 'done' && job.status !== 'error'

  const load = useCallback(async () => {
    const s = await getSession(sessionId)
    setSegments(s.segments)
    setJd(s.jd_text)
    setHasMedia(!!s.media_path)
    setDirty(false)
  }, [sessionId])

  useEffect(() => {
    let live = true
    setLoading(true)
    load()
      .catch((e: Error) => live && setError(e.message))
      .finally(() => live && setLoading(false))
    return () => {
      live = false
      abortRef.current?.abort()
    }
  }, [load])

  const edit = (i: number, patch: Partial<Segment>) => {
    setSegments((cur) => cur.map((s, j) => (j === i ? { ...s, ...patch } : s)))
    setDirty(true)
    setSavedNote(false)
  }

  const save = async (): Promise<boolean> => {
    setSaving(true)
    setError(null)
    try {
      await patchTranscript(sessionId, toSegmentIn(segments))
      setDirty(false)
      setSavedNote(true)
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    } finally {
      setSaving(false)
    }
  }

  const runJob = async (kind: 'transcribe' | 'analyze', start: () => Promise<{ job_id: string }>) => {
    setError(null)
    setJob({ kind, status: 'queued' })
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      const { job_id } = await start()
      const final: Job = await pollJob(sessionId, job_id, {
        intervalMs: 1000,
        signal: ctrl.signal,
        onUpdate: (j) => setJob({ kind, status: j.status }),
      })
      if (final.status === 'error') {
        setError(final.error_message || jobStatusMessage('error'))
        return
      }
      if (kind === 'transcribe') {
        await load()
      } else if (final.status === 'done') {
        onAnalyzed()
      } else {
        setError(`Analysis ended unexpectedly (${final.status}).`)
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      setError((e as Error).message)
    } finally {
      if (!ctrl.signal.aborted) setJob(null)
    }
  }

  const transcribe = () => {
    if (dirty && !window.confirm('Transcribing replaces the current transcript, including unsaved edits. Continue?'))
      return
    void runJob('transcribe', () => startTranscribe(sessionId))
  }

  const analyze = async () => {
    if (dirty && !(await save())) return
    await runJob('analyze', () => startAnalyze(sessionId))
  }

  const analyzable = canAnalyze(jd, segments)
  let analyzeHint = ''
  if (!jd.trim()) analyzeHint = 'Add a job description in Setup to analyze.'
  else if (segments.length === 0) analyzeHint = 'Add a transcript to analyze.'

  if (loading) {
    return (
      <section className="step-in">
        <h2>Transcript studio</h2>
        <p className="muted">Loading transcript…</p>
      </section>
    )
  }

  return (
    <section className="step-in studio">
      <h2>Transcript studio</h2>
      <p className="muted">Fix speaker labels and wording before analyzing — click a chip to change the speaker.</p>

      {job && (
        <p className="notice progress-pulse" role="status" aria-live="polite">
          {jobStatusMessage(job.status)}
        </p>
      )}
      {error && (
        <p className="notice" role="alert">
          {error}
        </p>
      )}

      {segments.length === 0 ? (
        <div className="panel empty">
          <p>Paste a transcript or run transcription</p>
          {hasMedia ? (
            <button type="button" className="btn" disabled={busy} onClick={transcribe}>
              Transcribe recording
            </button>
          ) : (
            <button type="button" className="btn" onClick={onBack}>
              Back to setup
            </button>
          )}
        </div>
      ) : (
        <ol className="segment-list" style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.6rem' }}>
          {segments.map((s, i) => (
            <li
              key={s.id || i}
              className="panel segment"
              style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.5rem 0.9rem', alignItems: 'start' }}
            >
              <div style={{ display: 'grid', gap: '0.35rem', justifyItems: 'start' }}>
                <button
                  type="button"
                  className={`btn btn-sm speaker-chip speaker-${s.speaker} ${s.speaker === 'unknown' ? 'btn-ghost' : ''}`}
                  aria-label={`Speaker for segment ${i + 1}: ${SPEAKER_LABEL[s.speaker]}. Click to change.`}
                  disabled={busy}
                  onClick={() => edit(i, { speaker: nextSpeaker(s.speaker) })}
                >
                  {SPEAKER_LABEL[s.speaker]}
                </button>
                <span className="muted" style={{ fontSize: '0.75rem' }}>
                  {formatMs(s.start_ms)}
                </span>
              </div>
              <textarea
                className="field"
                rows={Math.max(2, Math.ceil(s.text.length / 90))}
                aria-label={`Text for segment ${i + 1}`}
                value={s.text}
                disabled={busy}
                onChange={(e) => edit(i, { text: e.target.value })}
              />
            </li>
          ))}
        </ol>
      )}

      <div className="setup-actions" style={{ marginTop: '1rem', flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-ghost" onClick={onBack} disabled={busy || saving}>
          Back
        </button>
        <span className="hint" aria-live="polite">
          {analyzeHint || (dirty ? 'Unsaved changes.' : savedNote ? 'Saved.' : '')}
        </span>
        {hasMedia && segments.length > 0 && (
          <button type="button" className="btn btn-ghost" disabled={busy || saving} onClick={transcribe}>
            Re-transcribe
          </button>
        )}
        <button
          type="button"
          className="btn btn-ghost"
          disabled={busy || saving || !dirty || segments.length === 0}
          onClick={() => void save()}
        >
          {saving ? 'Saving…' : 'Save transcript'}
        </button>
        <button
          type="button"
          className="btn"
          disabled={busy || saving || !analyzable}
          onClick={() => void analyze()}
        >
          Analyze
        </button>
      </div>
    </section>
  )
}
