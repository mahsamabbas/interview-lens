import type { SourceType } from './api'

export const MIN_JD_CHARS = 40

export interface SetupDraft {
  jd: string
  source: SourceType | null
  file: File | null
  paste: string
}

/** Source already persisted on the session (return visit from transcript). */
export interface ExistingSessionSource {
  sourceType: SourceType | null
  hasMedia: boolean
  hasSegments: boolean
}

export function jdValid(jd: string): boolean {
  return jd.trim().length >= MIN_JD_CHARS
}

export function sourceAttached(d: Pick<SetupDraft, 'source' | 'file' | 'paste'>): boolean {
  if (d.source === 'sample_video') return true
  if (d.source === 'upload') return d.file !== null
  if (d.source === 'paste') return d.paste.trim().length > 0
  return false
}

export function hasExistingSource(ex: ExistingSessionSource): boolean {
  if (!ex.sourceType) return false
  if (ex.sourceType === 'upload') return ex.hasMedia
  return ex.hasSegments
}

/** True when Continue should call sample/paste/upload APIs. */
export function sourceNeedsIngest(d: SetupDraft, ex: ExistingSessionSource): boolean {
  if (!hasExistingSource(ex)) return sourceAttached(d)
  if (d.source !== ex.sourceType) return true
  if (d.source === 'upload' && d.file !== null) return true
  if (d.source === 'paste' && d.paste.trim().length > 0) return true
  return false
}

export function canContinue(d: SetupDraft, ex?: ExistingSessionSource): boolean {
  if (!jdValid(d.jd)) return false
  const existing = ex ?? { sourceType: null, hasMedia: false, hasSegments: false }
  if (hasExistingSource(existing) && !sourceNeedsIngest(d, existing)) return true
  return sourceAttached(d)
}

export const STEPS = [
  { key: 'setup', label: 'Setup' },
  { key: 'transcript', label: 'Transcript' },
  { key: 'reports', label: 'Reports' },
] as const

export type StepKey = (typeof STEPS)[number]['key']
export type AppStep = 'home' | StepKey
