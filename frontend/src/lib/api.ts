export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ??
  'http://localhost:8004'

export type Speaker = 'interviewer' | 'candidate' | 'unknown'
export type Recommendation = 'pass' | 'borderline' | 'no'
export type JobStatus =
  | 'queued'
  | 'transcribing'
  | 'diarizing'
  | 'ready'
  | 'analyzing'
  | 'done'
  | 'error'
export type SourceType = 'sample_video' | 'upload' | 'paste'
export type JobKind = 'transcribe' | 'analyze'

export interface Health {
  ok: boolean
  status: string
  ollama: boolean
  whisper_ready: boolean
  hf_token_set: boolean
}

export interface SessionSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
  status: string
  source_type: SourceType | null
}

export interface Segment {
  id: string
  session_id: string
  idx: number
  start_ms: number
  end_ms: number
  speaker: Speaker
  text: string
}

export interface SegmentIn {
  idx: number
  start_ms: number
  end_ms: number
  speaker: Speaker
  text: string
}

export interface Session extends SessionSummary {
  jd_text: string
  media_path: string | null
  segments: Segment[]
}

export interface Job {
  id: string
  session_id: string
  kind: JobKind
  status: JobStatus
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ScoreItem {
  score: number
  rationale: string
}

export interface ScoreBlock {
  jd_match: ScoreItem
  answer_depth: ScoreItem
  communication: ScoreItem
  structure: ScoreItem
  overall: ScoreItem
}

export interface CandidateReport {
  scores: ScoreBlock
  summary: string
  strengths: { point: string; evidence_quote: string }[]
  improvements: { point: string; evidence_quote: string; tip: string }[]
  question_notes: { topic_or_question: string; note: string; evidence_quote: string }[]
  readiness_note: string
  unknowns: string[]
}

export interface HiringReport {
  scores: ScoreBlock
  recommendation: Recommendation
  hire_confidence: number
  fit_summary: string
  skill_evidence: { skill: string; evidence_quote: string }[]
  gaps: { skill_or_requirement: string; note: string }[]
  red_flags: { note: string; evidence_quote: string }[]
  follow_up_questions: string[]
  unknowns: string[]
  disclaimer: string
}

export interface Reports {
  candidate: CandidateReport
  hiring: HiringReport
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
      else if (body?.detail) detail = JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

function jsonInit(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }
}

const sid = (id: string) => encodeURIComponent(id)

/** GET /health */
export const getHealth = () => request<Health>('/health')

/** GET /sessions */
export const listSessions = () => request<SessionSummary[]>('/sessions')

/** POST /sessions */
export const createSession = (title: string) =>
  request<{ id: string }>('/sessions', jsonInit('POST', { title }))

/** GET /sessions/{id} */
export const getSession = (id: string) => request<Session>(`/sessions/${sid(id)}`)

/** PUT /sessions/{id}/jd */
export const putJd = (id: string, jdText: string) =>
  request<{ ok: boolean }>(`/sessions/${sid(id)}/jd`, jsonInit('PUT', { jd_text: jdText }))

/** POST /sessions/{id}/source/paste */
export const sourcePaste = (id: string, text: string) =>
  request<{ ok: boolean; segments: number }>(
    `/sessions/${sid(id)}/source/paste`,
    jsonInit('POST', { text }),
  )

/** POST /sessions/{id}/source/sample */
export const sourceSample = (id: string) =>
  request<{ ok: boolean; segments: number }>(`/sessions/${sid(id)}/source/sample`, {
    method: 'POST',
  })

/** POST /sessions/{id}/source/upload (multipart, field `file`) */
export const sourceUpload = (id: string, file: File) => {
  const form = new FormData()
  form.append('file', file)
  return request<{ ok: boolean; media_path: string }>(`/sessions/${sid(id)}/source/upload`, {
    method: 'POST',
    body: form,
  })
}

/** POST /sessions/{id}/transcribe */
export const startTranscribe = (id: string) =>
  request<{ job_id: string }>(`/sessions/${sid(id)}/transcribe`, { method: 'POST' })

/** GET /sessions/{id}/jobs/{job_id} */
export const getJob = (id: string, jobId: string) =>
  request<Job>(`/sessions/${sid(id)}/jobs/${encodeURIComponent(jobId)}`)

/** PATCH /sessions/{id}/transcript */
export const patchTranscript = (id: string, segments: SegmentIn[]) =>
  request<{ ok: boolean; segments: number }>(
    `/sessions/${sid(id)}/transcript`,
    jsonInit('PATCH', { segments }),
  )

/** POST /sessions/{id}/analyze */
export const startAnalyze = (id: string) =>
  request<{ job_id: string }>(`/sessions/${sid(id)}/analyze`, { method: 'POST' })

/** GET /sessions/{id}/reports */
export const getReports = (id: string) => request<Reports>(`/sessions/${sid(id)}/reports`)

const TERMINAL: JobStatus[] = ['ready', 'done', 'error']

/** Poll a job until it reaches ready/done/error (or the signal aborts). */
export async function pollJob(
  sessionId: string,
  jobId: string,
  opts: { intervalMs?: number; onUpdate?: (job: Job) => void; signal?: AbortSignal } = {},
): Promise<Job> {
  const { intervalMs = 1200, onUpdate, signal } = opts
  for (;;) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    const job = await getJob(sessionId, jobId)
    onUpdate?.(job)
    if (TERMINAL.includes(job.status)) return job
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}
