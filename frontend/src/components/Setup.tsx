import { useEffect, useRef, useState } from 'react'
import {
  createSession,
  getSession,
  putJd,
  sourcePaste,
  sourceSample,
  sourceUpload,
  type SourceType,
} from '../lib/api'
import { canContinue, jdValid, MIN_JD_CHARS, sourceAttached } from '../lib/setup'

interface Props {
  sessionId: string | null
  onBack: () => void
  onReady: (sessionId: string) => void
}

const SOURCES: { key: SourceType; title: string; blurb: string }[] = [
  { key: 'sample_video', title: 'Sample', blurb: 'Use the bundled demo interview.' },
  { key: 'upload', title: 'Upload', blurb: 'Audio or video of the interview recording.' },
  { key: 'paste', title: 'Paste', blurb: 'Paste a transcript you already have.' },
]

function titleFromJd(jd: string): string {
  const first = jd.trim().split('\n')[0].trim()
  return (first.length > 60 ? `${first.slice(0, 57)}…` : first) || 'Interview review'
}

export default function Setup({ sessionId, onBack, onReady }: Props) {
  const [jd, setJd] = useState('')
  const [source, setSource] = useState<SourceType | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [paste, setPaste] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const jdFileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!sessionId) return
    let live = true
    getSession(sessionId)
      .then((s) => live && setJd((cur) => cur || s.jd_text || ''))
      .catch(() => undefined)
    return () => {
      live = false
    }
  }, [sessionId])

  const draft = { jd, source, file, paste }
  const ok = canContinue(draft)

  const loadJdFile = async (f: File | undefined) => {
    if (!f) return
    setJd(await f.text())
    if (jdFileRef.current) jdFileRef.current.value = ''
  }

  const submit = async () => {
    if (!ok || busy) return
    setError(null)
    try {
      setBusy('Creating your session…')
      const id = sessionId ?? (await createSession(titleFromJd(jd))).id
      setBusy('Saving job description…')
      await putJd(id, jd.trim())
      if (source === 'sample_video') {
        setBusy('Loading the sample interview…')
        await sourceSample(id)
      } else if (source === 'paste') {
        setBusy('Reading your transcript…')
        await sourcePaste(id, paste)
      } else if (source === 'upload' && file) {
        setBusy('Uploading the recording…')
        await sourceUpload(id, file)
      }
      onReady(id)
    } catch (e) {
      setError((e as Error).message)
      setBusy(null)
    }
  }

  const jdLen = jd.trim().length
  let hint = 'Ready when you are.'
  if (!jdValid(jd)) hint = `Add at least ${MIN_JD_CHARS - jdLen} more characters to the job description.`
  else if (!sourceAttached(draft)) hint = 'Choose an interview source to continue.'

  return (
    <section className="step-in setup">
      <h2>Set up your review</h2>
      <p className="muted">Two things: what the role needs, and the interview itself.</p>

      <div className="panel setup-block">
        <div className="setup-head">
          <label htmlFor="jd">Job description</label>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => jdFileRef.current?.click()}>
            Load .txt / .md file
          </button>
          <input
            ref={jdFileRef}
            type="file"
            accept=".txt,.md,text/plain,text/markdown"
            hidden
            aria-label="Job description file"
            onChange={(e) => void loadJdFile(e.target.files?.[0])}
          />
        </div>
        <textarea
          id="jd"
          className="field"
          rows={8}
          value={jd}
          placeholder="Paste the role’s responsibilities and required skills…"
          onChange={(e) => setJd(e.target.value)}
        />
        <p className={`counter ${jdValid(jd) ? 'ok' : ''}`}>
          {jdLen} / {MIN_JD_CHARS} characters minimum
        </p>
      </div>

      <div className="panel setup-block">
        <div className="setup-head">
          <span className="label">Interview recording</span>
        </div>
        <div className="source-cards" role="radiogroup" aria-label="Interview source">
          {SOURCES.map((s) => (
            <button
              key={s.key}
              type="button"
              role="radio"
              aria-checked={source === s.key}
              className={`source-card ${source === s.key ? 'is-selected' : ''}`}
              onClick={() => setSource(s.key)}
            >
              <strong>{s.title}</strong>
              <span>{s.blurb}</span>
            </button>
          ))}
        </div>

        {source === 'upload' && (
          <label className="source-detail">
            <span className="muted">{file ? `Selected: ${file.name}` : 'No file chosen yet.'}</span>
            <input
              className="field"
              type="file"
              accept="audio/*,video/*"
              aria-label="Interview recording file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
        )}
        {source === 'paste' && (
          <div className="source-detail">
            <textarea
              className="field"
              rows={7}
              aria-label="Transcript text"
              value={paste}
              placeholder={'Interviewer: Tell me about…\nCandidate: Sure, at my last role…'}
              onChange={(e) => setPaste(e.target.value)}
            />
          </div>
        )}
        {source === 'sample_video' && (
          <p className="source-detail muted">The demo interview will be loaded for you.</p>
        )}
      </div>

      {error && (
        <p className="notice" role="alert">
          {error}
        </p>
      )}

      <div className="setup-actions">
        <button type="button" className="btn btn-ghost" onClick={onBack} disabled={!!busy}>
          Back
        </button>
        <span className="hint" aria-live="polite">
          {busy ?? hint}
        </span>
        <button type="button" className="btn" disabled={!ok || !!busy} onClick={() => void submit()}>
          Continue to transcript
        </button>
      </div>
    </section>
  )
}
